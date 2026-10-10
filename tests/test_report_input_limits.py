"""The citizen-report endpoints are public, so what they accept must be bounded: an
oversized photo must not be read into memory first, a stored file's extension must not be
chosen by the client, and free-text / coordinate fields need limits. No database."""
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import reports as reports_router
from app.schemas import MAX_DESCRIPTION_CHARS, CitizenReportIn

client = TestClient(app)


class RecordingFile(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def _photo(data=b"x" * 10, filename="a.jpg", content_type="image/jpeg"):
    return SimpleNamespace(file=RecordingFile(data), filename=filename, content_type=content_type)


def test_an_oversized_photo_is_rejected_after_reading_at_most_one_byte_past_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "max_photo_size_bytes", 100)
    photo = _photo(b"x" * 5000)
    with pytest.raises(HTTPException) as e:
        reports_router._save_photo(photo)
    assert e.value.status_code == 422
    assert photo.file.read_sizes == [101]  # never the whole 5000 bytes, never an unbounded read()


def test_a_photo_exactly_at_the_limit_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "max_photo_size_bytes", 100)
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "k")
    monkeypatch.setattr(reports_router.httpx, "post", lambda *a, **kw: SimpleNamespace(status_code=200, text=""))
    assert reports_router._save_photo(_photo(b"x" * 100)).startswith("https://example.supabase.co/")


def test_the_stored_extension_comes_from_the_content_type_not_the_client_filename(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "k")
    uploads = []
    monkeypatch.setattr(
        reports_router.httpx, "post", lambda url, **kw: uploads.append(url) or SimpleNamespace(status_code=200, text="")
    )
    public_url = reports_router._save_photo(_photo(filename="evil.html", content_type="image/png"))
    assert uploads[0].endswith(".png") and "evil" not in uploads[0] and ".html" not in uploads[0]
    assert public_url.endswith(".png")


def test_a_disallowed_content_type_is_still_refused():
    with pytest.raises(HTTPException) as e:
        reports_router._save_photo(_photo(filename="x.html", content_type="text/html"))
    assert e.value.status_code == 422


VALID = {"reportType": "crack", "severity": "low", "placeName": "Pelling", "description": "A crack on the road", "capturedAt": "2026-10-10T08:00:00Z"}


def _post(data):
    return client.post("/reports", data={"data": json.dumps(data)})


def test_a_normal_report_still_validates():
    CitizenReportIn.model_validate_json(json.dumps({**VALID, "coords": {"lat": 27.3, "lng": 88.6, "accuracy": 12.5}}))


@pytest.mark.parametrize(
    "change",
    [
        {"description": "x" * (MAX_DESCRIPTION_CHARS + 1)},
        {"placeName": "p" * 201},
        {"reporterName": "n" * 101},
        {"reporterPhone": "9" * 33},
        {"coords": {"lat": 91, "lng": 88}},
        {"coords": {"lat": 27, "lng": -181}},
        {"coords": {"lat": 27, "lng": 88, "accuracy": -1}},
    ],
)
def test_out_of_bounds_report_fields_are_rejected_before_anything_is_stored(change):
    assert _post({**VALID, **change}).status_code == 422


def test_the_ai_wording_assist_refuses_an_unbounded_description_before_calling_the_model(monkeypatch):
    monkeypatch.setattr(reports_router, "polish_description", lambda d: pytest.fail("the model must not be called"))
    assert client.post("/reports/polish-description", json={"description": "x" * (MAX_DESCRIPTION_CHARS + 1)}).status_code == 422
