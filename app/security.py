"""Officer access key for the API's write actions and personal-data reads.

One shared secret (`API_KEY` in the environment), sent by callers in an
`X-API-Key` header. Kept deliberately simple for a prototype with a handful of
officers -- no user accounts -- but it closes the real hole: without it, anyone
who found the backend URL could send real SMS/phone calls (broadcast, or a
rainfall fetch that trips the alert engine), overwrite risk scores, or read
citizens' names and phone numbers.

If `API_KEY` is not set the key is NOT enforced, so a deploy can never lock
anyone out before the key exists; GET /health reports which mode is active.
"""
import secrets
import time
from collections import deque

from fastapi import Header, HTTPException

from app.config import settings

# Failed attempts are throttled globally, not per client (behind Render's proxy
# a per-IP limit would need trusting a spoofable header). Correct keys are never
# throttled; a guesser is held to MAX_FAILURES per WINDOW_SECONDS, which makes
# even a weak key impractical to brute-force.
MAX_FAILURES = 20
WINDOW_SECONDS = 60
_failures: deque[float] = deque()


def auth_enabled() -> bool:
    return bool(settings.api_key)


def auth_headers() -> dict[str, str]:
    """For scripts that call this API: the header to send when a key is set."""
    return {"X-API-Key": settings.api_key} if settings.api_key else {}


def _reset_throttle() -> None:  # for tests
    _failures.clear()


def require_officer_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: raises 401 unless the request carries the key."""
    if not settings.api_key:
        return
    if x_api_key is not None and secrets.compare_digest(x_api_key.encode(), settings.api_key.encode()):
        return

    now = time.monotonic()
    while _failures and now - _failures[0] > WINDOW_SECONDS:
        _failures.popleft()
    if len(_failures) >= MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed attempts; try again in a minute")
    _failures.append(now)
    raise HTTPException(status_code=401, detail="Officer access key required", headers={"WWW-Authenticate": "ApiKey"})
