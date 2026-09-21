import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LandslideRecord
from app.schemas import CountOut, LandslideRecordOut, LandslideRecordsOut, LandslideSummaryOut

router = APIRouter(prefix="/landslide-records", tags=["landslide-records"])

_ORDER = (LandslideRecord.state, LandslideRecord.district, LandslideRecord.slide_name, LandslideRecord.id)
EXPORT_COLUMNS = ("state", "district", "slide_name", "location", "slide_no", "activity", "material", "movement", "history_note", "lat", "lng")


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
            .order_by(*_ORDER)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return LandslideRecordsOut(total=total, items=items)


def _safe_cell(value):
    """A spreadsheet runs a cell that starts with = + - @ as a formula; the survey's free
    text is not ours, so those are neutralised with a leading apostrophe."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@router.get("/export.csv")
def export_records(
    state: str | None = None,
    district: str | None = None,
    activity: str | None = None,
    q: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    """The same records and filters as the list, all of them, as a CSV file for
    Excel or a report (a state's inventory is a few hundred to a few thousand rows)."""
    rows = db.execute(select(LandslideRecord).where(*_filters(state, district, activity, q)).order_by(*_ORDER)).scalars().all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for r in rows:
        writer.writerow([_safe_cell(getattr(r, c)) for c in EXPORT_COLUMNS])
    name = f"landslide-records-{(state or 'all-states').lower().replace(' ', '-')}.csv"
    return Response(
        content="\ufeff" + out.getvalue(),  # BOM so Excel reads it as UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


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
