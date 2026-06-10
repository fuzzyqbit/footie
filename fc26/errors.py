"""Shared error types for fc26."""


class FC26Error(Exception):
    """Base class for fc26 errors."""


class DatabaseError(FC26Error):
    """The JSON store is unreadable or corrupt."""


class FetchError(FC26Error):
    """A network fetch failed after retry."""


class ParseError(FC26Error):
    """A page or document did not match the expected structure."""
