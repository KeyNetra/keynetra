"""Operational CLI for KeyNetra core."""

from __future__ import annotations

import asyncio
import json
import os
import time
import warnings
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import typer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from keynetra.config.config_loader import apply_config_to_environment, load_config_file
from keynetra.config.file_loaders import load_policies_from_paths
from keynetra.config.redis_client import get_redis
from keynetra.config.settings import DEFAULT_SERVER_HOST, get_settings, reset_settings_cache
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.infrastructure.cache.access_index_cache import build_access_index_cache
from keynetra.infrastructure.cache.acl_cache import build_acl_cache
from keynetra.infrastructure.cache.decision_cache import build_decision_cache
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.cache.relationship_cache import build_relationship_cache
from keynetra.infrastructure.repositories.acl import SqlACLRepository
from keynetra.infrastructure.repositories.audit import SqlAuditRepository
from keynetra.infrastructure.repositories.idempotency import SqlIdempotencyRepository
from keynetra.infrastructure.repositories.policies import SqlPolicyRepository
from keynetra.infrastructure.repositories.relationships import SqlRelationshipRepository
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.repositories.users import SqlUserRepository
from keynetra.infrastructure.storage.session import (
    create_engine_for_url,
    create_session_factory,
    initialize_database,
    run_migrations,
)
from keynetra.migrations import find_destructive_revisions
from keynetra.services.authorization import AuthorizationService
from keynetra.services.doctor import run_core_doctor
from keynetra.services.policy_testing import validate_policy_test_suite
from keynetra.services.seeding import seed_demo_data
from keynetra.version import __version__

# Keep CLI startup output focused; these Pydantic warnings are non-fatal.
warnings.filterwarnings(
    "ignore",
    message=r'Field name "schema" in "AuthModel(Create|Out)" shadows an attribute in parent "BaseModel"',
    category=UserWarning,
)

app = typer.Typer(add_completion=False, help="KeyNetra operational CLI.")
acl_app = typer.Typer(add_completion=False, help="Manage ACL entries.")
model_app = typer.Typer(add_completion=False, help="Manage authorization models.")
config_app = typer.Typer(add_completion=False, help="Configuration diagnostics.")
app.add_typer(acl_app, name="acl")
app.add_typer(model_app, name="model")
app.add_typer(config_app, name="config")


@app.callback()
def cli_root(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None, "--config", help="Path to YAML/JSON/TOML KeyNetra configuration file."
    ),
) -> None:
    if config:
        _load_config(config)
    ctx.obj = {"config": config}


def _load_config(path: str) -> None:
    cfg = load_config_file(path)
    apply_config_to_environment(cfg)
    os.environ["KEYNETRA_CONFIG"] = path
    reset_settings_cache()
    get_redis.cache_clear()


def _effective_config_path(ctx: typer.Context, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if isinstance(ctx.obj, dict):
        value = ctx.obj.get("config")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _maybe_load_config(ctx: typer.Context, path: str | None) -> None:
    effective = _effective_config_path(ctx, path)
    if effective:
        _load_config(effective)


def _resolve_url(explicit_url: str | None, suffix: str, *, use_settings: bool) -> str:
    if explicit_url:
        parsed = urlsplit(explicit_url)
        normalized_path = parsed.path.rstrip("/")
        if normalized_path.endswith(suffix):
            return explicit_url
        return urlunsplit(parsed._replace(path=f"{normalized_path}{suffix}"))
    if not use_settings:
        return f"http://localhost:8000{suffix}"
    settings = get_settings()
    host = settings.server_host
    if host == DEFAULT_SERVER_HOST:
        host = "127.0.0.1"
    return f"http://{host}:{settings.server_port}{suffix}"


@app.command("start")
def start(
    ctx: typer.Context,
    host: str = typer.Option(DEFAULT_SERVER_HOST, "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload", help="Enable development autoreload."),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Start the KeyNetra HTTP API (backward-compatible alias for serve)."""

    config_active = _effective_config_path(ctx, config) is not None
    _maybe_load_config(ctx, config)
    settings = get_settings()
    _run_server(
        host=host if not config_active or host != DEFAULT_SERVER_HOST else settings.server_host,
        port=port if not config_active or port != 8000 else settings.server_port,
        reload=reload,
    )


@app.command("serve")
def serve(
    ctx: typer.Context,
    host: str = typer.Option(DEFAULT_SERVER_HOST, "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload", help="Enable development autoreload."),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Start the KeyNetra HTTP API in headless config mode."""

    config_active = _effective_config_path(ctx, config) is not None
    _maybe_load_config(ctx, config)
    settings = get_settings()
    _run_server(
        host=host if not config_active or host != DEFAULT_SERVER_HOST else settings.server_host,
        port=port if not config_active or port != 8000 else settings.server_port,
        reload=reload,
    )


def _run_server(*, host: str, port: int, reload: bool) -> None:
    """Run the FastAPI app."""

    import uvicorn

    settings = get_settings()
    _render_startup_screen(
        host=host,
        port=port,
        reload=reload,
        settings=settings,
        config_path=os.getenv("KEYNETRA_CONFIG"),
    )
    os.environ["KEYNETRA_LOG_FORMAT"] = "rich"
    try:
        uvicorn.run(
            "keynetra.api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_config=None,
            access_log=True,
        )
    except TypeError:
        uvicorn.run("keynetra.api.main:app", host=host, port=port, reload=reload)


def _render_startup_screen(
    *, host: str, port: int, reload: bool, settings: Any, config_path: str | None
) -> None:
    try:
        from rich import box
        from rich.align import Align
        from rich.columns import Columns
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except ModuleNotFoundError:
        typer.echo(f"KeyNetra starting on http://{host}:{port} mode={settings.service_mode}")
        return

    force_color = os.getenv("KEYNETRA_FORCE_COLOR", "1").strip().lower() not in {"0", "false", "no"}
    console = Console(
        force_terminal=force_color, color_system="truecolor" if force_color else "auto"
    )
    banner = Text("KEYNETRA", style="bold magenta")
    try:
        import pyfiglet

        f = pyfiglet.figlet_format("KEYNETRA", font="slant")
        banner = Text(f, style="bold magenta")
    except (ImportError, RuntimeError, ValueError):
        banner = Text("KEYNETRA", style="bold magenta")

    header = Panel.fit(
        Align.center(
            Text.assemble(
                banner,
                "\n",
                ("Authorization Engine", "bold cyan"),
                "\n",
                (f"v{__version__}", "bold bright_white"),
            )
        ),
        border_style="bright_blue",
        padding=(0, 2),
        box=box.ROUNDED,
    )
    console.print(header)

    runtime = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_cyan",
        expand=True,
        pad_edge=False,
    )
    runtime.add_column("Runtime", style="bold white", width=14, no_wrap=True)
    runtime.add_column("Value", style="bright_white", overflow="fold")
    runtime.add_row("Mode", f"[bright_magenta]{settings.service_mode}[/bright_magenta]")
    runtime.add_row("Environment", f"[cyan]{settings.environment}[/cyan]")
    runtime.add_row("Server", f"[green]http://{host}:{port}[/green]")
    runtime.add_row("Reload", "[green]enabled[/green]" if reload else "[yellow]disabled[/yellow]")
    runtime.add_row("Config File", str(config_path or "not provided"))

    storage = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_green",
        expand=True,
        pad_edge=False,
    )
    storage.add_column("Storage", style="bold white", width=14, no_wrap=True)
    storage.add_column("Value", style="bright_white", overflow="fold")
    storage.add_row("Database", str(settings.database_url))
    storage.add_row("Redis", str(settings.redis_url or "disabled"))
    storage.add_row("Policy Paths", ", ".join(settings.parsed_policy_paths()) or "default")
    storage.add_row("Model Paths", ", ".join(settings.parsed_model_paths()) or "none")

    security = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold yellow",
        expand=True,
        pad_edge=False,
    )
    security.add_column("Security", style="bold white", width=14, no_wrap=True)
    security.add_column("Value", style="bright_white", overflow="fold")
    security.add_row("Auth", "api-key + jwt + admin-login")
    security.add_row("Admin User", str(settings.admin_username or "disabled"))
    security.add_row("Rate Limit", f"{settings.rate_limit_per_minute}/min")

    panel_width = max(60, console.width - 2)
    if console.width < 140:
        console.print(
            Panel(
                runtime,
                title="Runtime",
                border_style="bright_cyan",
                box=box.ROUNDED,
                width=panel_width,
            )
        )
        console.print(
            Panel(
                storage,
                title="Storage",
                border_style="bright_green",
                box=box.ROUNDED,
                width=panel_width,
            )
        )
        console.print(
            Panel(
                security,
                title="Security",
                border_style="yellow",
                box=box.ROUNDED,
                width=panel_width,
            )
        )
    else:
        console.print(Columns([runtime, storage, security], equal=True, expand=True))
    console.print(
        Panel(
            "[bold green]Startup complete[/bold green]  •  [cyan]launching uvicorn[/cyan]",
            border_style="green",
            box=box.MINIMAL_HEAVY_HEAD,
        )
    )


@app.command("version")
def version() -> None:
    """Print the KeyNetra core version."""

    typer.echo(__version__)


@app.command("admin-login")
def admin_login(
    ctx: typer.Context,
    username: str = typer.Option(..., "--username"),
    password: str = typer.Option(..., "--password"),
    url: str | None = typer.Option(None, "--url"),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Get admin JWT using username/password."""

    config_active = _effective_config_path(ctx, config) is not None
    _maybe_load_config(ctx, config)
    resp = httpx.post(
        _resolve_url(url, "/admin/login", use_settings=config_active),
        json={"username": username, "password": password},
        timeout=10.0,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    typer.echo(resp.text)


@app.command("help-cli")
def help_cli() -> None:
    """Print a complete CLI quick reference with headless config examples."""

    typer.echo(
        "\n".join(
            [
                "KeyNetra CLI Help",
                "",
                "Global option:",
                "  --config <path>   Load YAML/JSON/TOML config file",
                "",
                "Core commands:",
                "  keynetra serve --config examples/keynetra.yaml",
                "  keynetra start --host 0.0.0.0 --port 8000",
                "  keynetra version",
                "  keynetra admin-login --username admin --password admin123 [--config ...]",
                "  keynetra migrate [--config ...]",
                "  keynetra seed-data [--reset] [--config ...]",
                '  keynetra check --api-key devkey --action read --user \'{"id":"u1"}\' --resource \'{"resource_type":"document","resource_id":"doc-1"}\' [--config ...]',
                '  keynetra simulate --api-key devkey --policy-change \'{"action":"read","effect":"allow","priority":10,"conditions":{"role":"admin"}}\' --action read [--config ...]',
                '  keynetra impact --api-key devkey --policy-change \'{"action":"read","effect":"deny","priority":1,"conditions":{}}\' [--config ...]',
                "  keynetra explain --user u1 --resource doc-1 --action read [--config ...]",
                "  keynetra test-policy examples/policy_tests.yaml",
                "  keynetra compile-policies --config examples/keynetra.yaml",
                "  keynetra doctor --service core [--config ...]",
                "  keynetra benchmark --api-key devkey",
                "",
                "ACL commands:",
                "  keynetra acl add --subject-type user --subject-id u1 --resource-type document --resource-id doc-1 --action read --effect allow",
                "  keynetra acl list --resource-type document --resource-id doc-1",
                "  keynetra acl remove --acl-id 1",
                "",
                "Model commands:",
                "  keynetra model apply examples/auth-model.yaml --api-key devkey",
                "  keynetra model show --api-key devkey",
                "",
                "Headless config file examples:",
                "  examples/keynetra.yaml",
                "  examples/auth-model.yaml",
                "  examples/policies/",
                "",
                "Embedded usage:",
                "  from keynetra import KeyNetra",
                "  engine = KeyNetra.from_config('examples/keynetra.yaml')",
                "  decision = engine.check_access(subject='user:1', action='read', resource='document:abc')",
            ]
        )
    )


@app.command("migrate")
def migrate(
    ctx: typer.Context,
    revision: str = typer.Option("head", "--revision", help="Alembic revision to upgrade to."),
    confirm_destructive: bool = typer.Option(
        False, "--confirm-destructive", help="Allow migrations that drop tables or columns."
    ),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Apply database migrations for the configured KeyNetra database."""
    _maybe_load_config(ctx, config)

    from alembic.config import Config

    core_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(core_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(core_dir / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", get_settings().database_url)
    engine = create_engine_for_url(get_settings().database_url)
    versions_dir = core_dir / "alembic" / "versions"
    applied = _read_applied_revisions(engine)
    destructive = find_destructive_revisions(versions_dir, applied)
    if destructive and not confirm_destructive:
        typer.echo("Destructive migrations detected:")
        for revision_id in destructive:
            typer.echo(f"  - {revision_id}")
        typer.echo("Re-run with --confirm-destructive to apply them.")
        raise typer.Exit(code=1)

    run_migrations(get_settings().database_url, revision=revision)
    typer.echo(f"Migrations applied to {revision}.")


@app.command("purge-idempotency")
def purge_idempotency(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Delete expired idempotency records for scheduled maintenance jobs."""
    _maybe_load_config(ctx, config)

    settings = get_settings()
    initialize_database(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    db = session_factory()
    try:
        deleted = SqlIdempotencyRepository(db).delete_expired()
    finally:
        db.close()
    typer.echo(json.dumps({"deleted": deleted}, indent=2))


@app.command("seed-data")
def seed_data(
    ctx: typer.Context,
    reset: bool = typer.Option(
        False, "--reset", help="Clear the sample dataset before seeding it again."
    ),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Seed deterministic sample data for local development and smoke tests."""
    _maybe_load_config(ctx, config)

    settings = get_settings()
    initialize_database(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    db = session_factory()
    try:
        summary = seed_demo_data(db, reset=reset)
    finally:
        db.close()

    typer.echo(
        json.dumps(
            {
                "tenant_key": summary.tenant_key,
                "created_tenant": summary.created_tenant,
                "created_user": summary.created_user,
                "created_role": summary.created_role,
                "created_permissions": summary.created_permissions,
                "created_relationships": summary.created_relationships,
                "created_policies": summary.created_policies,
            },
            indent=2,
        )
    )


@app.command("check")
def check(
    ctx: typer.Context,
    url: str | None = typer.Option(None, "--url"),
    api_key: str = typer.Option(..., "--api-key"),
    user: str = typer.Option("{}", "--user", help="JSON object"),
    action: str = typer.Option(..., "--action"),
    resource: str = typer.Option("{}", "--resource", help="JSON object"),
    context: str = typer.Option("{}", "--context", help="JSON object"),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Send one authorization request to a running KeyNetra server."""
    config_active = _effective_config_path(ctx, config) is not None
    _maybe_load_config(ctx, config)

    user_obj: dict[str, Any] = json.loads(user)
    res_obj: dict[str, Any] = json.loads(resource)
    context_obj: dict[str, Any] = json.loads(context)
    payload = {"user": user_obj, "action": action, "resource": res_obj, "context": context_obj}
    headers = {"X-API-Key": api_key}
    resp = httpx.post(
        _resolve_url(url, "/check-access", use_settings=config_active),
        json=payload,
        headers=headers,
        timeout=10.0,
    )
    resp.raise_for_status()
    typer.echo(resp.text)


@model_app.command("apply")
def model_apply(
    file: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Schema DSL file"
    ),
    url: str = typer.Option("http://localhost:8000/auth-model", "--url"),
    api_key: str = typer.Option(..., "--api-key"),
) -> None:
    schema = file.read_text(encoding="utf-8")
    resp = httpx.post(url, json={"schema": schema}, headers={"X-API-Key": api_key}, timeout=10.0)
    resp.raise_for_status()
    typer.echo(resp.text)


@model_app.command("show")
def model_show(
    url: str = typer.Option("http://localhost:8000/auth-model", "--url"),
    api_key: str = typer.Option(..., "--api-key"),
) -> None:
    resp = httpx.get(url, headers={"X-API-Key": api_key}, timeout=10.0)
    resp.raise_for_status()
    typer.echo(resp.text)


@app.command("simulate")
def simulate(
    ctx: typer.Context,
    policy_change: str = typer.Option(..., "--policy-change"),
    user: str = typer.Option("{}", "--user", help="JSON object"),
    action: str = typer.Option(..., "--action"),
    resource: str = typer.Option("{}", "--resource", help="JSON object"),
    context: str = typer.Option("{}", "--context", help="JSON object"),
    url: str | None = typer.Option(None, "--url"),
    api_key: str = typer.Option(..., "--api-key"),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    config_active = _effective_config_path(ctx, config) is not None
    _maybe_load_config(ctx, config)
    payload = {
        "simulate": {"policy_change": policy_change},
        "request": {
            "user": json.loads(user),
            "action": action,
            "resource": json.loads(resource),
            "context": json.loads(context),
        },
    }
    resp = httpx.post(
        _resolve_url(url, "/simulate-policy", use_settings=config_active),
        json=payload,
        headers={"X-API-Key": api_key},
        timeout=10.0,
    )
    resp.raise_for_status()
    typer.echo(resp.text)


@app.command("impact")
def impact(
    ctx: typer.Context,
    policy_change: str = typer.Option(..., "--policy-change"),
    url: str | None = typer.Option(None, "--url"),
    api_key: str = typer.Option(..., "--api-key"),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    config_active = _effective_config_path(ctx, config) is not None
    _maybe_load_config(ctx, config)
    resp = httpx.post(
        _resolve_url(url, "/impact-analysis", use_settings=config_active),
        json={"policy_change": policy_change},
        headers={"X-API-Key": api_key},
        timeout=10.0,
    )
    resp.raise_for_status()
    typer.echo(resp.text)


@app.command("explain")
def explain(
    ctx: typer.Context,
    user: str = typer.Option(..., "--user", help="User id."),
    resource: str = typer.Option(..., "--resource", help="Resource id."),
    action: str = typer.Option(..., "--action"),
    context: str = typer.Option("{}", "--context", help="JSON object"),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Evaluate one decision locally and print the explanation trace."""
    _maybe_load_config(ctx, config)

    settings = get_settings()
    initialize_database(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    db = session_factory()
    try:
        tenants = SqlTenantRepository(db)
        if tenants.get_by_key(DEFAULT_TENANT_KEY) is None:
            tenants.create(DEFAULT_TENANT_KEY)
        service = _build_authorization_service(db)
        result = service.authorize(
            tenant_key=DEFAULT_TENANT_KEY,
            principal={"type": "cli", "id": "cli"},
            user={"id": _coerce_scalar(user)},
            action=action,
            resource={"id": _coerce_scalar(resource)},
            context=json.loads(context),
            audit=False,
        )
    finally:
        db.close()

    typer.echo(
        json.dumps(
            {
                "allowed": result.decision.allowed,
                "decision": result.decision.decision,
                "reason": result.decision.reason,
                "policy_id": result.decision.policy_id,
                "matched_policies": list(result.decision.matched_policies),
                "explain_trace": [step.to_dict() for step in result.decision.explain_trace],
            },
            indent=2,
        )
    )


@app.command("test-policy")
def test_policy(
    file: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="YAML or JSON policy test file"
    ),
) -> None:
    """Validate policies and execute deterministic policy tests before deployment."""

    document = file.read_text(encoding="utf-8")
    results = validate_policy_test_suite(document)
    failures = [result for result in results if not result.passed]

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"[{status}] {result.name}: expected={result.expected} actual={result.actual} "
            f"policy_id={result.policy_id or '-'} reason={result.reason or '-'}"
        )

    if failures:
        raise typer.Exit(code=1)


@app.command("compile-policies")
def compile_policies(
    ctx: typer.Context,
    path: list[str] | None = typer.Option(
        None,
        "--path",
        help="Policy file or directory path. Repeat --path for multiple values.",
    ),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Compile policies from files and print a deterministic summary."""

    _maybe_load_config(ctx, config)
    settings = get_settings()
    configured_paths = path or settings.parsed_policy_paths()
    if not configured_paths:
        raise typer.BadParameter("no policy paths configured")

    policies = load_policies_from_paths(configured_paths)
    if not policies:
        raise typer.BadParameter("no policy definitions found")

    from keynetra.engine.keynetra_engine import KeyNetraEngine

    engine = KeyNetraEngine(policies)
    typer.echo(
        json.dumps(
            {
                "compiled_policies": len(policies),
                "strategy": "first_match",
                "policy_ids": [
                    policy.policy_id or f"{policy.action}:{policy.priority}:{policy.effect}"
                    for policy in engine._policies  # noqa: SLF001
                ],
            },
            indent=2,
        )
    )


@app.command("generate-openapi")
def generate_openapi(
    output: str = typer.Option(
        "contracts/openapi.json", "--output", help="OpenAPI output file path."
    ),
    yaml_output: str | None = typer.Option(
        None, "--yaml-output", help="Optional YAML OpenAPI output file path."
    ),
) -> None:
    """Generate OpenAPI contract directly from the FastAPI app."""
    from typing import Protocol, cast

    from keynetra.main import create_app

    app_instance = create_app()
    payload = app_instance.openapi()

    class _YamlModule(Protocol):
        def safe_dump(self, data: object, *, sort_keys: bool = ...) -> str: ...

    try:
        import yaml as _yaml
    except ModuleNotFoundError as exc:
        raise typer.BadParameter("pyyaml is required to generate yaml contracts") from exc
    yaml = cast(_YamlModule, _yaml)

    written_paths: list[str] = []
    for raw_path in [output, yaml_output]:
        if raw_path is None:
            continue
        out_path = Path(raw_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.suffix.lower() == ".json":
            out_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        else:
            out_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        written_paths.append(str(out_path))
    typer.echo(json.dumps({"written": written_paths}, indent=2))


@app.command("check-openapi")
def check_openapi(
    contract: str = typer.Option(
        "contracts/openapi.json",
        "--contract",
        help="Versioned OpenAPI contract to compare against generated output.",
    ),
) -> None:
    """Fail if generated OpenAPI differs from the versioned contract."""
    from keynetra.main import create_app

    app_instance = create_app()
    payload = app_instance.openapi()
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise typer.BadParameter("pyyaml is required to check yaml contracts") from exc

    path = Path(contract)
    if not path.exists():
        raise typer.BadParameter(f"contract file not found: {path}")
    expected = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        expected_payload = json.loads(expected)
        ok = payload == expected_payload
    else:
        expected_payload = yaml.safe_load(expected)
        ok = payload == expected_payload
    if not ok:
        typer.echo(
            json.dumps(
                {
                    "ok": False,
                    "message": "OpenAPI contract drift detected.",
                    "contract": str(path),
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)
    typer.echo(json.dumps({"ok": True, "contract": str(path)}, indent=2))


@app.command("doctor")
def doctor(
    ctx: typer.Context,
    service: str = typer.Option("core", "--service", help="Deployment to validate: core or saas."),
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Validate production readiness for core or SaaS deployments."""
    _maybe_load_config(ctx, config)

    normalized_service = service.strip().lower()
    if normalized_service == "core":
        result = run_core_doctor(get_settings())
    elif normalized_service == "saas":
        try:
            from saas.backend.src.config.settings import get_settings as get_saas_settings
            from saas.backend.src.services.doctor import run_saas_doctor
        except ModuleNotFoundError as exc:
            raise typer.BadParameter("SaaS backend is not importable in this environment.") from exc
        result = run_saas_doctor(get_saas_settings())
    else:
        raise typer.BadParameter("service must be one of: core, saas")

    typer.echo(json.dumps(result, indent=2))
    if not result["ok"]:
        raise typer.Exit(code=1)


@config_app.command("doctor")
def config_doctor(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", help="Path to config file."),
) -> None:
    """Validate runtime configuration and print explicit remediation guidance."""
    _maybe_load_config(ctx, config)
    settings = get_settings()
    result = run_core_doctor(settings)
    findings: list[dict[str, Any]] = []
    for check in result.get("checks", []):
        details = check.get("details") or {}
        remediation = details.get("remediation") if isinstance(details, dict) else None
        if check.get("ok"):
            continue
        findings.append(
            {
                "check": check.get("name"),
                "message": check.get("message"),
                "remediation": remediation if isinstance(remediation, list) else [],
            }
        )
    typer.echo(
        json.dumps(
            {
                "service": "core",
                "ok": result.get("ok", False),
                "environment": settings.environment,
                "findings": findings,
            },
            indent=2,
        )
    )
    if findings:
        raise typer.Exit(code=1)


async def _run_benchmark(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    total: int,
    concurrency: int,
    timeout: float,
) -> list[float]:
    durations: list[float] = []
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=timeout) as client:

        async def send_request() -> None:
            async with sem:
                start = time.perf_counter()
                response = await client.post(url, json=payload, headers=headers)
                elapsed = time.perf_counter() - start
                response.raise_for_status()
                durations.append(elapsed)

        await asyncio.gather(*(send_request() for _ in range(total)))
    return durations


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    lower = int(k)
    upper = min(lower + 1, len(sorted_vals) - 1)
    weight = k - lower
    return (1 - weight) * sorted_vals[lower] + weight * sorted_vals[upper]


@app.command("benchmark")
def benchmark(
    url: str = typer.Option("http://localhost:8000/check-access", "--url"),
    requests: int = typer.Option(100, "--requests"),
    concurrency: int = typer.Option(10, "--concurrency"),
    api_key: str = typer.Option(..., "--api-key"),
    timeout: float = typer.Option(10.0, "--timeout"),
) -> None:
    """Measure latency and throughput against the authorization API."""

    if requests < 1:
        raise typer.BadParameter("requests must be greater than zero")
    if concurrency < 1:
        raise typer.BadParameter("concurrency must be greater than zero")
    payload = {"user": {"id": 1}, "action": "check", "resource": {"amount": 1}, "context": {}}
    headers = {"X-API-Key": api_key}
    durations = asyncio.run(_run_benchmark(url, payload, headers, requests, concurrency, timeout))
    if not durations:
        typer.echo("No successful samples collected.")
        raise typer.Exit(code=1)
    total_time = sum(durations)
    throughput = len(durations) / total_time if total_time > 0 else 0.0
    result = {
        "requests": len(durations),
        "p50(ms)": _percentile(durations, 50) * 1000,
        "p95(ms)": _percentile(durations, 95) * 1000,
        "p99(ms)": _percentile(durations, 99) * 1000,
        "throughput": throughput,
    }
    typer.echo(json.dumps(result, indent=2))


@acl_app.command("add")
def acl_add(
    subject_type: str = typer.Option(..., "--subject-type"),
    subject_id: str = typer.Option(..., "--subject-id"),
    resource_type: str = typer.Option(..., "--resource-type"),
    resource_id: str = typer.Option(..., "--resource-id"),
    action: str = typer.Option(..., "--action"),
    effect: str = typer.Option(..., "--effect"),
    tenant_key: str = typer.Option(DEFAULT_TENANT_KEY, "--tenant-key"),
) -> None:
    settings = get_settings()
    initialize_database(settings.database_url)
    db = create_session_factory(settings.database_url)()
    redis_client = get_redis()
    try:
        tenants = SqlTenantRepository(db)
        tenant = tenants.get_or_create(tenant_key)
        acl_repo = SqlACLRepository(db)
        acl_id = acl_repo.create_acl_entry(
            tenant_id=tenant.id,
            subject_type=subject_type,
            subject_id=subject_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            effect=effect,
        )
        build_acl_cache(redis_client).invalidate(
            tenant_id=tenant.id, resource_type=resource_type, resource_id=resource_id
        )
        build_access_index_cache(redis_client).invalidate_tenant(tenant_id=tenant.id)
        build_decision_cache(redis_client).bump_namespace(tenant_key)
        typer.echo(json.dumps({"acl_id": acl_id, "tenant_key": tenant_key}, indent=2))
    finally:
        db.close()


@acl_app.command("list")
def acl_list(
    resource_type: str = typer.Option(..., "--resource-type"),
    resource_id: str = typer.Option(..., "--resource-id"),
    tenant_key: str = typer.Option(DEFAULT_TENANT_KEY, "--tenant-key"),
) -> None:
    settings = get_settings()
    initialize_database(settings.database_url)
    db = create_session_factory(settings.database_url)()
    try:
        tenant = SqlTenantRepository(db).get_or_create(tenant_key)
        rows = SqlACLRepository(db).list_resource_acl(
            tenant_id=tenant.id, resource_type=resource_type, resource_id=resource_id
        )
        typer.echo(json.dumps([row.to_dict() for row in rows], indent=2, default=str))
    finally:
        db.close()


@acl_app.command("remove")
def acl_remove(
    acl_id: int = typer.Option(..., "--acl-id"),
    tenant_key: str = typer.Option(DEFAULT_TENANT_KEY, "--tenant-key"),
) -> None:
    settings = get_settings()
    initialize_database(settings.database_url)
    db = create_session_factory(settings.database_url)()
    redis_client = get_redis()
    try:
        tenants = SqlTenantRepository(db)
        tenant = tenants.get_or_create(tenant_key)
        repo = SqlACLRepository(db)
        target = repo.get_acl_entry(tenant_id=tenant.id, acl_id=acl_id)
        repo.delete_acl_entry(tenant_id=tenant.id, acl_id=acl_id)
        if target is not None:
            build_acl_cache(redis_client).invalidate(
                tenant_id=tenant.id,
                resource_type=target.resource_type,
                resource_id=target.resource_id,
            )
            build_access_index_cache(redis_client).invalidate_tenant(tenant_id=tenant.id)
        build_decision_cache(redis_client).bump_namespace(tenant_key)
        typer.echo(json.dumps({"acl_id": acl_id, "tenant_key": tenant_key}, indent=2))
    finally:
        db.close()


def _read_applied_revisions(engine) -> set[str]:
    try:
        with engine.connect() as connection:
            return {
                str(revision)
                for revision in connection.execute(text("SELECT version_num FROM alembic_version"))
                .scalars()
                .all()
            }
    except (SQLAlchemyError, Exception):
        return set()


def _build_authorization_service(db: Session) -> AuthorizationService:
    redis_client = get_redis()
    return AuthorizationService(
        settings=get_settings(),
        tenants=SqlTenantRepository(db),
        policies=SqlPolicyRepository(db),
        users=SqlUserRepository(db),
        relationships=SqlRelationshipRepository(db),
        audit=SqlAuditRepository(db),
        policy_cache=build_policy_cache(redis_client),
        relationship_cache=build_relationship_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        acl_repository=SqlACLRepository(db),
        acl_cache=build_acl_cache(redis_client),
        access_index_cache=build_access_index_cache(redis_client),
    )


def _coerce_scalar(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def main() -> None:
    app()


if __name__ == "__main__":
    main()
