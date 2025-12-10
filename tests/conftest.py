"""Test configuration and shared fixtures."""

import pytest
import asyncio
from src.core.engine import EventBus


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def bus():
    """Create a fresh EventBus for each test."""
    return EventBus()
