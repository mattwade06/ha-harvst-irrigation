"""Shared pytest fixtures."""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make our custom_components/harvst discoverable by Home Assistant in tests."""
    yield
