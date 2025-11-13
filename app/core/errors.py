"""Core exception classes for the application."""


class RecordAlreadyExistsError(Exception):
    """Raised when trying to create a record that already exists."""


class NotFoundError(Exception):
    """Raised when a resource is not found."""


class ValidationError(Exception):
    """Raised when validation fails."""
