import pathlib
import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import CitizenReport
from app.schemas import CitizenReportIn, CitizenReportOut

router = APIRouter(prefix="/reports", tags=["citizen-reports"])


def _save_photo(photo: UploadFile) -> str:
    """Uploads to Supabase Storage (a plain REST call via httpx -- already
    a dependency, no need for the full supabase-py SDK just for this) and
    returns the public URL. Not local disk: a deployed host's filesystem
    (e.g. Render's free tier) is ephemeral and wipes on every restart."""
    if photo.content_type not in settings.allowed_photo_content_types:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported photo content type {photo.content_type!r}, "
                   f"expected one of {settings.allowed_photo_content_types}",
        )

    contents = photo.file.read()
    if len(contents) > settings.max_photo_size_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"photo too large ({len(contents)} bytes), "
                   f"max is {settings.max_photo_size_bytes} bytes",
        )

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=500,
            detail="photo upload is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing)",
        )

    extension = pathlib.Path(photo.filename or "").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{extension}"
    upload_url = f"{settings.supabase_url}/storage/v1/object/{settings.supabase_storage_bucket}/{filename}"

    response = httpx.post(
        upload_url,
        content=contents,
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": photo.content_type,
        },
        timeout=30.0,
    )
    if response.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Supabase Storage upload failed: {response.status_code} {response.text[:200]}",
        )

    return f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_storage_bucket}/{filename}"


@router.post("", response_model=CitizenReportOut)
def submit_report(
    data: str = Form(..., description="JSON string matching CitizenReportIn's field names"),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Citizen report submission: multipart/form-data with a `data` field
    (JSON string, see CitizenReportIn) and an optional `photo` file, in one
    request -- matches what the reporting frontend already sends."""
    try:
        payload = CitizenReportIn.model_validate_json(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    if payload.client_report_id is not None:
        existing = (
            db.query(CitizenReport)
            .filter(CitizenReport.client_report_id == payload.client_report_id)
            .first()
        )
        if existing is not None:
            return existing  # idempotent: retried submission, don't duplicate

    photo_url = _save_photo(photo) if photo is not None else None

    report = CitizenReport(
        client_report_id=payload.client_report_id,
        zone_id=payload.zone_id,
        report_type=payload.report_type,
        severity=payload.severity,
        geo_lat=payload.coords.lat if payload.coords else None,
        geo_lng=payload.coords.lng if payload.coords else None,
        geo_accuracy_m=payload.coords.accuracy if payload.coords else None,
        place_name=payload.place_name,
        description=payload.description,
        reporter_name=payload.reporter_name,
        reporter_phone=payload.reporter_phone,
        photo_url=photo_url,
        captured_at=payload.captured_at,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[CitizenReportOut])
def list_reports(db: Session = Depends(get_db)):
    return db.query(CitizenReport).order_by(CitizenReport.submitted_at.desc()).all()
