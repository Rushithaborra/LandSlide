from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CitizenReport
from app.schemas import CitizenReportIn, CitizenReportOut

router = APIRouter(prefix="/reports", tags=["citizen-reports"])


@router.post("", response_model=CitizenReportOut)
def submit_report(payload: CitizenReportIn, db: Session = Depends(get_db)):
    """Citizen report submission: form -> backend -> dashboard. photo_url is
    expected to already be an uploaded file URL — this endpoint doesn't handle
    the upload itself."""
    report = CitizenReport(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[CitizenReportOut])
def list_reports(db: Session = Depends(get_db)):
    return db.query(CitizenReport).order_by(CitizenReport.submitted_at.desc()).all()
