import pytest

from app.routers import zones as zones_router


@pytest.fixture(autouse=True)
def _fresh_monitored_cache():
    # _monitored_ids() caches select_zones() for a minute; many tests stub
    # select_zones per test, so a result cached by one must never leak into the next.
    zones_router.clear_monitored_cache()
    yield
    zones_router.clear_monitored_cache()
