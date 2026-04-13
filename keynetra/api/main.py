import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from keynetra.api.middleware.errors import register_error_handlers
from keynetra.api.middleware.idempotency import IdempotencyMiddleware
from keynetra.api.middleware.logging import RequestLoggingMiddleware
from keynetra.api.openapi import build_openapi_schema
from keynetra.api.middleware.request_id import RequestIdMiddleware
from keynetra.api.middleware.tenant import TenantResolverMiddleware
from keynetra.api.middleware.versioning import ApiVersionMiddleware
from keynetra.api.service_modes import router_for_mode
from keynetra.config.rate_limit import RateLimitMiddleware
from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings, get_settings
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.engine.compiled.decision_graph import COMPILED_POLICY_STORE
from keynetra.engine.keynetra_engine import KeyNetraEngine
from keynetra.engine.model_graph.permission_graph import MODEL_GRAPH_STORE, CompiledPermissionGraph
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.errors import BootstrapError
from keynetra.infrastructure.logging import configure_json_logging, log_event
from keynetra.infrastructure.storage.session import create_session_factory, initialize_database
from keynetra.modeling.permission_compiler import compile_authorization_schema
from keynetra.observability.metrics import record_bootstrap_failure
from keynetra.services.seeding import seed_demo_data
from keynetra.version import version as keynetra_version

_bootstrap_logger = logging.getLogger("keynetra.bootstrap")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _run_startup(settings)
    _start_policy_subscriber(app, settings=settings)
    try:
        yield
    finally:
        _stop_policy_subscriber(app)


def create_app() -> FastAPI:
    configure_json_logging()
    app = FastAPI(title="KeyNetra", version=keynetra_version, lifespan=_lifespan)
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_allow_origins(),
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.parsed_cors_allow_methods(),
        allow_headers=settings.parsed_cors_allow_headers(),
    )
    app.add_middleware(IdempotencyMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantResolverMiddleware)
    app.add_middleware(ApiVersionMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app, settings)

    mode = getattr(settings, "service_mode", "all")
    app.include_router(router_for_mode(mode))

    if getattr(settings, "otel_enabled", False):
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except ImportError:
            log_event(_bootstrap_logger, event="otel_disabled", reason="instrumentor_not_installed")
        except RuntimeError as exc:
            record_bootstrap_failure(stage="otel")
            log_event(_bootstrap_logger, event="otel_init_failed", reason=repr(exc))
            if settings.environment in {"prod", "production"}:
                raise BootstrapError("failed to initialize OTel instrumentation") from exc

    app.openapi = lambda: build_openapi_schema(app)
    return app


def _run_startup(settings: Settings) -> None:
    try:
        initialize_database(settings.database_url)
    except Exception as exc:
        record_bootstrap_failure(stage="database")
        log_event(_bootstrap_logger, event="bootstrap_database_failed", reason=repr(exc))
        raise BootstrapError("database initialization failed") from exc
    _bootstrap_file_backed_policies(settings)
    _bootstrap_file_backed_model(settings)
    if settings.environment.strip().lower() not in {"development", "dev", "local"}:
        return
    if not getattr(settings, "auto_seed_sample_data", False):
        return
    mode = getattr(settings, "service_mode", "all").strip().lower()
    if mode not in {"all", "policy-store"}:
        return
    db = create_session_factory(settings.database_url)()
    try:
        seed_demo_data(db)
    finally:
        db.close()


def _start_policy_subscriber(app: FastAPI, *, settings: Settings | None = None) -> None:
    if settings is None:
        settings = get_settings()
    policy_cache = build_policy_cache(get_redis())
    try:
        import json
        import threading

        r = get_redis()
        if r is None:
            return

        pubsub = r.pubsub()
        pubsub.subscribe(settings.policy_events_channel)

        def run() -> None:
            for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    payload = json.loads(msg.get("data"))
                    tenant_key = payload.get("tenant_key")
                    if isinstance(tenant_key, str):
                        policy_cache.invalidate(tenant_key)
                except (TypeError, ValueError) as exc:
                    log_event(
                        _bootstrap_logger,
                        event="policy_subscriber_message_invalid",
                        reason=repr(exc),
                    )
                    continue

        t = threading.Thread(target=run, name="policy-subscriber", daemon=True)
        t.start()
        app.state.policy_pubsub = pubsub
        app.state.policy_subscriber = t
    except ImportError as exc:
        log_event(_bootstrap_logger, event="policy_subscriber_unavailable", reason=repr(exc))
        return
    except RuntimeError as exc:
        record_bootstrap_failure(stage="policy_subscriber")
        log_event(_bootstrap_logger, event="policy_subscriber_failed", reason=repr(exc))
        if settings.environment in {"prod", "production"}:
            raise BootstrapError("policy subscriber startup failed") from exc


def _stop_policy_subscriber(app: FastAPI) -> None:
    pubsub = getattr(app.state, "policy_pubsub", None)
    if pubsub is None:
        return
    try:
        pubsub.close()
    except (RuntimeError, OSError, ValueError) as exc:
        log_event(_bootstrap_logger, event="policy_subscriber_close_failed", reason=repr(exc))


def _bootstrap_file_backed_model(settings: Settings | None = None) -> None:
    if settings is None:
        settings = get_settings()
    model_paths = settings.parsed_model_paths()
    if not model_paths:
        return
    try:
        from keynetra.config.file_loaders import load_authorization_model_from_paths

        schema = load_authorization_model_from_paths(model_paths)
        if not schema:
            return
        compiled = compile_authorization_schema(schema)
        MODEL_GRAPH_STORE.set(
            DEFAULT_TENANT_KEY,
            CompiledPermissionGraph(tenant_key=DEFAULT_TENANT_KEY, model=compiled),
        )
    except (ValueError, RuntimeError) as exc:
        record_bootstrap_failure(stage="model_bootstrap")
        log_event(_bootstrap_logger, event="model_bootstrap_failed", reason=repr(exc))
        if str(getattr(settings, "environment", "development")).strip().lower() in {
            "prod",
            "production",
        }:
            raise BootstrapError("authorization model bootstrap failed") from exc


def _bootstrap_file_backed_policies(settings: Settings | None = None) -> None:
    if settings is None:
        settings = get_settings()
    try:
        policies = settings.load_policies()
        engine = KeyNetraEngine(policies)
        COMPILED_POLICY_STORE.set(DEFAULT_TENANT_KEY, 1, engine._compiled_graph)
    except (ValueError, RuntimeError) as exc:
        record_bootstrap_failure(stage="policy_bootstrap")
        log_event(_bootstrap_logger, event="policy_bootstrap_failed", reason=repr(exc))
        if str(getattr(settings, "environment", "development")).strip().lower() in {
            "prod",
            "production",
        }:
            raise BootstrapError("policy bootstrap failed") from exc


app = create_app()
