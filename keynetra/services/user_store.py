"""Deprecated compatibility import.

Database-backed user lookup now lives in
``keynetra.infrastructure.repositories.users``.
"""

from keynetra.infrastructure.repositories.users import SqlUserRepository as UserStore

__all__ = ["UserStore"]
