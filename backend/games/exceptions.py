"""Exceptions for game and round lifecycle operations (M06)."""


class GameError(Exception):
    """Base exception for all game operations."""
    pass


class InvalidInputError(GameError, ValueError):
    """Raised when an operation receives invalid input (e.g. non-integer answer, out of bounds)."""
    pass


class InvalidStateError(GameError):
    """Raised when an operation is attempted in an invalid or inadmissible game/round state."""
    pass


class RecordNotFoundError(GameError):
    """Raised when an expected database record does not exist (e.g. missing question, bank exhausted)."""
    pass
