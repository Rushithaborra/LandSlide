"""The IMD API client, against a fake IMD server (httpx.MockTransport) -- nothing real is called."""
import httpx
import pytest
from pydantic import SecretStr

from app.services import imd

KEY, EMAIL, PASSWORD = "key-SECRET", "team@example.org", "pw-SECRET"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(imd.settings, "imd_api_key", SecretStr(KEY))
    monkeypatch.setattr(imd.settings, "imd_email", EMAIL)
    monkeypatch.setattr(imd.settings, "imd_password", SecretStr(PASSWORD))
    imd.reset_token()
    yield
    imd.reset_token()


class FakeImd:
    """Issues numbered tokens; an endpoint call is valid only with the latest token."""

    def __init__(self, expires_in=3600, reject_first_call=False):
        self.token_calls = 0
        self.api_calls = 0
        self.expires_in = expires_in
        self.reject_first_call = reject_first_call
        self.seen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token.php"):
            body = request.read().decode()
            assert EMAIL in body and PASSWORD in body
            self.token_calls += 1
            return httpx.Response(200, json={"access_token": f"tok{self.token_calls}", "token_type": "Bearer", "expires_in": self.expires_in})
        self.api_calls += 1
        self.seen.append(dict(request.headers))
        if self.reject_first_call and self.api_calls == 1:
            return httpx.Response(401, json={"error": "expired"})
        return httpx.Response(200, json=[{"district": "Kamrup", "day1_color": "yellow"}])


def client_for(fake):
    return httpx.Client(transport=httpx.MockTransport(fake))


def test_a_call_sends_the_key_and_a_bearer_token_and_returns_the_json():
    fake = FakeImd()
    data = imd.call("districtwarning", {"id": 164}, client=client_for(fake))
    assert data == [{"district": "Kamrup", "day1_color": "yellow"}]
    assert fake.seen[0]["x-api-key"] == KEY and fake.seen[0]["authorization"] == "Bearer tok1"


def test_the_token_is_reused_until_it_is_about_to_expire():
    fake = FakeImd()
    c = client_for(fake)
    imd.call("districtwarning", client=c)
    imd.call("districtrainfall", client=c)
    assert fake.token_calls == 1 and fake.api_calls == 2


def test_a_token_that_expires_soon_is_replaced_before_use():
    fake = FakeImd(expires_in=30)  # inside the safety margin
    c = client_for(fake)
    imd.call("districtwarning", client=c)
    imd.call("districtwarning", client=c)
    assert fake.token_calls == 2


def test_a_401_gets_a_fresh_token_and_exactly_one_retry():
    fake = FakeImd(reject_first_call=True)
    assert imd.call("districtwarning", client=client_for(fake))
    assert fake.token_calls == 2 and fake.api_calls == 2 and fake.seen[1]["authorization"] == "Bearer tok2"


def test_a_persistent_401_is_an_error_not_a_loop():
    def always_401(request):
        if request.url.path.endswith("/oauth/token.php"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(401)

    with pytest.raises(imd.ImdError, match="HTTP 401"):
        imd.call("districtwarning", client=httpx.Client(transport=httpx.MockTransport(always_401)))


@pytest.mark.parametrize("missing", ["imd_api_key", "imd_email", "imd_password"])
def test_missing_credentials_are_reported_before_any_request(monkeypatch, missing):
    monkeypatch.setattr(imd.settings, missing, None)
    fake = FakeImd()
    with pytest.raises(imd.ImdNotConfigured):
        imd.call("districtwarning", client=client_for(fake))
    assert fake.token_calls == 0 and fake.api_calls == 0


def test_no_secret_appears_in_an_error_or_in_the_settings_repr():
    def token_refused(request):
        return httpx.Response(403, json={"echo": f"{EMAIL} {PASSWORD} {KEY}"})

    with pytest.raises(imd.ImdError) as error:
        imd.call("districtwarning", client=httpx.Client(transport=httpx.MockTransport(token_refused)))
    for secret in (KEY, PASSWORD, EMAIL):
        assert secret not in str(error.value)
    assert KEY not in repr(imd.settings) and PASSWORD not in repr(imd.settings)
