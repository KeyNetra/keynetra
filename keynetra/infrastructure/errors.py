from __future__ import annotations


class KeyNetraError(Exception):
    """Base class for classified service errors."""


class BootstrapError(KeyNetraError):
    """Raised when startup/bootstrap fails and service must fail-fast."""


class ConfigurationError(KeyNetraError):
    """Raised for invalid runtime configuration."""
