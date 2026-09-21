from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LandslideRecord
from app.schemas import CountOut, LandslideRecordOut, LandslideRecordsOut, LandslideSummaryOut

router = APIRouter(prefix="/landslide-records", tags=["landslide-records"])


def _filters(state: str | None, district: str | None, activity: str | None, q: str | None) -> list:
    conditions = []
    if state:
        conditions.append(LandslideRecord.state == state)
    if district:
        conditions.append(LandslideRecord.district == district)
    if activity:
        conditions.append(LandslideRecord.activity == activity)
    if q and q.strip():
        # A plain substring search; %, _ and \ typed by the user are matched literally.
        term = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(
            or_(*(col.ilike(term, escape="\\") for col in (LandslideRecord.slide_name, LandslideRecord.location, LandslideRecord.district, LandslideRecord.slide_no)))
        )
    return conditions


@router.get("", response_model=LandslideRecordsOut)
def list_records(
    state: str | None = None,
    district: str | None = None,
    activity: str | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Real GSI landslide records, filtered and paged. Public: these are published
    government inventory records, not personal data."""
    conditions = _filters(state, district, activity, q)
    total = db.scalar(select(func.count()).select_from(LandslideRecord).where(*conditions)) or 0
    items = (
        db.execute(
            select(LandslideRecord)
            .where(*conditions)
            .order_by(LandslideRecord.state, LandslideRecord.district, LandslideRecord.slide_name, LandslideRecord.id)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return LandslideRecordsOut(total=total, items=items)


@router.get("/summary", response_model=LandslideSummaryOut)
def records_summary(state: str | None = None, db: Session = Depends(get_db)):
    """What is loaded for a state (or all): the total, and counts per district and per
    activity status -- feeds the page's filters and tells the dashboard whether a
    state's records have been loaded at all."""
    where = [LandslideRecord.state == state] if state else []

    def counts(column):
        rows = db.execute(select(column, func.count()).where(*where, column.isnot(None)).group_by(column).order_by(func.count().desc(), column)).all()
        return [CountOut(name=name, count=n) for name, n in rows]

    total = db.scalar(select(func.count()).select_from(LandslideRecord).where(*where)) or 0
    return LandslideSummaryOut(total=total, districts=counts(LandslideRecord.district), activities=counts(LandslideRecord.activity))
