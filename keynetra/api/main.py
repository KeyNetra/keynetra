from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from keynetra.api.middleware.admin import AdminAuthorizationContextMiddleware
from keynetra.api.middleware.errors import register_error_handlers
from keynetra.api.middleware.idempotency import IdempotencyMiddleware
from keynetra.api.middleware.logging import RequestLoggingMiddleware
from keynetra.api.middleware.request_id import RequestIdMiddleware
from keynetra.api.middleware.versioning import ApiVersionMiddleware
from keynetra.api.service_modes import router_for_mode
from keynetra.config.rate_limit import RateLimitMiddleware
from keynetra.config.redis_client import get_redis
from keynetra.config.settings import get_settings
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.engine.compiled.decision_graph import COMPILED_POLICY_STORE
from keynetra.engine.keynetra_engine import KeyNetraEngine
from keynetra.engine.model_graph.permission_graph import MODEL_GRAPH_STORE, CompiledPermissionGraph
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.logging import configure_json_logging
from keynetra.infrastructure.storage.session import (
    create_session_factory,
    initialize_database,
)
from keynetra.modeling.permission_compiler import compile_authorization_schema
from keynetra.services.seeding import seed_demo_data
from keynetra.version import version as keynetra_version


def create_app() -> FastAPI:
    configure_json_logging()
    app = FastAPI(title="KeyNetra", version=keynetra_version)
    settings = get_settings()

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ApiVersionMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AdminAuthorizationContextMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(IdempotencyMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_allow_origins(),
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.parsed_cors_allow_methods(),
        allow_headers=settings.parsed_cors_allow_headers(),
    )
    register_error_handlers(app, settings)

    mode = getattr(settings, "service_mode", "all")
    app.include_router(router_for_mode(mode))

    if getattr(settings, "otel_enabled", False):
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            pass

    @app.on_event("startup")
    def _bootstrap_sample_data() -> None:
        initialize_database(settings.database_url)
        _bootstrap_file_backed_policies()
        _bootstrap_file_backed_model()
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

    _start_policy_subscriber(app)
    return app


def _start_policy_subscriber(app: FastAPI) -> None:
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
                except Exception:
                    continue

        t = threading.Thread(target=run, name="policy-subscriber", daemon=True)
        t.start()
        app.state.policy_subscriber = t
    except Exception:
        return


def _bootstrap_file_backed_model() -> None:
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
    except Exception:
        return


def _bootstrap_file_backed_policies() -> None:
    settings = get_settings()
    try:
        policies = settings.load_policies()
        engine = KeyNetraEngine(policies)
        COMPILED_POLICY_STORE.set(DEFAULT_TENANT_KEY, 1, engine._compiled_graph)
    except Exception:
        return


app = create_app()
