from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from time import perf_counter

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from keynetra.config.settings import get_settings
from keynetra.observability.metrics import observe_db_query_latency


def _operation_name(statement: str) -> str:
    first = (statement or "").strip().split(" ", 1)[0].upper()
    return first if first else "UNKNOWN"


@listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(  # pragma: no cover - sqlalchemy runtime hook
    conn, cursor, statement, parameters, context, executemany
) -> None:
    conn.info.setdefault("_query_start_times", []).append(perf_counter())


@listens_for(Engine, "after_cursor_execute")
def _after_cursor_execute(  # pragma: no cover - sqlalchemy runtime hook
    conn, cursor, statement, parameters, context, executemany
) -> None:
    starts = conn.info.get("_query_start_times", [])
    if not starts:
        return
    started_at = starts.pop()
    observe_db_query_latency(
        operation=_operation_name(statement), value=perf_counter() - started_at
    )


@lru_cache
def create_engine_for_url(database_url: str) -> Engine:
    # Shared in-memory sqlite connection is required for deterministic tests.
    if (
        database_url.startswith("sqlite+pysqlite:///:memory:")
        or database_url == "sqlite:///:memory:"
    ):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    return create_engine(database_url, pool_pre_ping=True, future=True)


@lru_cache
def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine_for_url(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@lru_cache
def initialize_database(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return

    from keynetra.domain.models import acl as _acl  # noqa: F401
    from keynetra.domain.models import audit as _audit  # noqa: F401
    from keynetra.domain.models import api_key as _api_key  # noqa: F401
    from keynetra.domain.models import auth_model as _auth_model  # noqa: F401
    from keynetra.domain.models import idempotency as _idempotency  # noqa: F401
    from keynetra.domain.models import policy_versioning as _policy_versioning  # noqa: F401
    from keynetra.domain.models import rbac as _rbac  # noqa: F401
    from keynetra.domain.models import relationship as _relationship  # noqa: F401
    from keynetra.domain.models import tenant as _tenant  # noqa: F401
    from keynetra.domain.models.base import Base

    engine = create_engine_for_url(database_url)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    settings = get_settings()
    initialize_database(settings.database_url)
    SessionLocal = create_session_factory(settings.database_url)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
