import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def isolate_cache():
    """Throttle counters belong to each test's client, not earlier test methods."""
    cache.clear()
    yield
    cache.clear()
