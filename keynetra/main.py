"""Backward-compatible module entrypoint.

Use `keynetra.api.main` for the canonical HTTP transport layer.
"""

from keynetra.api.main import app, create_app

__all__ = ["app", "create_app"]
