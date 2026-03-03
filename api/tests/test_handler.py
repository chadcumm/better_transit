"""Tests for Lambda handler."""


def test_handler_is_callable():
    from better_transit.handler import handler
    assert callable(handler)


def test_handler_wraps_app():
    """Handler delegates to Mangum which wraps the FastAPI app."""
    from better_transit.handler import handler
    from better_transit.main import app
    assert handler.app is app
