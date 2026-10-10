import pytest

from app.routers import rainfall as rainfall_router
from app.routers import zones as zones_router


@pytest.fixture(autouse=True)
def _fresh_monitored_cache():
    # _monitored_ids() caches select_zones() for a minute, and /rainfall/headroom caches its
    # whole answer; many tests stub select_zones per test, so a result cached by one must
    # never leak into the next.
    zones_router.clear_monitored_cache()
    rainfall_router.clear_headroom_cache()
    yield
    zones_router.clear_monitored_cache()
    rainfall_router.clear_headroom_cache()
