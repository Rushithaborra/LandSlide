"""Client for the India Meteorological Department API portal (https://api.imd.gov.in).

Every call sends two headers: `X-API-KEY` (the key, which IMD binds to one registered server
IP, so it only works from that machine) and `Authorization: Bearer <JWT>`, where the JWT is
minted by POSTing the portal account's email and password to the token endpoint and expires
(the portal's example says 3600 s). The token is cached until shortly before it expires and
refreshed once on a 401. Credentials come from settings (IMD_API_KEY, IMD_EMAIL,
IMD_PASSWORD) and are never logged or put in an error message.

Nothing else in the system calls this yet; see scripts/imd_probe.py for the read-only test.
"""
import time

import httpx

from app.config import settings

BASE_URL = "https://api.imd.gov.in"
TOKEN_URL = f"{BASE_URL}/api/oauth/token.php"
TIMEOUT_SECONDS = 30
TOKEN_MARGIN_SECONDS = 60  # refresh a little early rather than send a token that is about to expire

_token: dict = {"value": None, "expires_at": 0.0}


class ImdNotConfigured(RuntimeError):
    """IMD_API_KEY, IMD_EMAIL or IMD_PASSWORD is not set."""


class ImdError(RuntimeError):
    """IMD refused or failed a request. The message never contains a credential."""


def _credentials() -> tuple[str, str, str]:
    key, email, password = settings.imd_api_key, settings.imd_email, settings.imd_password
    if not (key and email and password):
        raise ImdNotConfigured("IMD_API_KEY, IMD_EMAIL and IMD_PASSWORD must all be set")
    return key.get_secret_value(), email, password.get_secret_value()


def reset_token() -> None:
    _token.update(value=None, expires_at=0.0)


def get_token(client: httpx.Client) -> str:
    """A valid JWT: the cached one, or a fresh one from the token endpoint."""
    if _token["value"] and time.time() < _token["expires_at"] - TOKEN_MARGIN_SECONDS:
        return _token["value"]
    _, email, password = _credentials()
    response = client.post(TOKEN_URL, json={"email": email, "password": password}, timeout=TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise ImdError(f"IMD token request failed (HTTP {response.status_code})")
    body = response.json()
    token = body.get("access_token")
    if not token:
        raise ImdError("IMD token response had no access_token")
    _token.update(value=token, expires_at=time.time() + float(body.get("expires_in") or 3600))
    return token


def call(endpoint: str, params: dict | None = None, client: httpx.Client | None = None):
    """GET one IMD API endpoint, e.g. call("districtwarning", {"id": 164}); returns the parsed JSON."""
    api_key = _credentials()[0]
    owns_client = client is None
    client = client or httpx.Client()
    try:
        for attempt in (1, 2):
            headers = {"X-API-KEY": api_key, "Authorization": f"Bearer {get_token(client)}"}
            response = client.get(f"{BASE_URL}/api/v1/{endpoint}", params=params or None, headers=headers, timeout=TIMEOUT_SECONDS)
            if response.status_code == 401 and attempt == 1:
                reset_token()  # expired or revoked: mint a new one and try once more
                continue
            if response.status_code != 200:
                raise ImdError(f"IMD {endpoint} failed (HTTP {response.status_code})")
            return response.json()
    finally:
        if owns_client:
            client.close()
