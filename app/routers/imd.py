from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImdWarning
from app.schemas import ImdWarningDayOut, ImdWarningDistrictOut, ImdWarningsIn, ImdWarningsOut
from app.security import require_officer_key

router = APIRouter(prefix="/imd", tags=["imd"])

# IMD's rain-warning codes (its API reference): 2 heavy, 16 very heavy, 17 extremely heavy rain.
RAIN_KINDS = {2: "heavy", 16: "very_heavy", 17: "extremely_heavy"}
SEVERITY = ("heavy", "very_heavy", "extremely_heavy")


@router.post("/warnings", dependencies=[Depends(require_officer_key)])
def replace_warnings(payload: ImdWarningsIn, db: Session = Depends(get_db)):
    """Replace the stored IMD snapshot with a freshly fetched one (officer key). The whole
    snapshot is swapped in one transaction, so a failed push leaves the previous one."""
    db.execute(delete(ImdWarning))
    db.add_all(
        ImdWarning(
            state=r.state, district=r.district, obj_id=r.obj_id, day=r.day, valid_date=r.valid_date,
            codes=",".join(str(c) for c in sorted(set(r.codes))), color=r.color, issued_at=payload.issued_at,
        )
        for r in payload.rows
    )
    db.commit()
    return {"stored": len(payload.rows)}


@router.get("/warnings", response_model=ImdWarningsOut)
def list_warnings(state: str | None = None, db: Session = Depends(get_db)):
    """The rain warnings in the latest IMD snapshot, for one state or all. Public. It says
    when IMD issued them and how many districts IMD's feed lists here, so an empty list can
    be told apart from a state IMD's feed does not cover. These are rainfall warnings,
    not landslide alerts."""
    where = [ImdWarning.state == state] if state else []
    rows = db.execute(select(ImdWarning).where(*where).order_by(ImdWarning.state, ImdWarning.district, ImdWarning.day)).scalars().all()
    if not rows:
        any_snapshot = db.scalar(select(func.count()).select_from(ImdWarning))
        if not any_snapshot:
            return ImdWarningsOut(issued_at=None, fetched_at=None, districts_covered=0, districts=[])
        newest = db.execute(select(func.max(ImdWarning.issued_at), func.max(ImdWarning.fetched_at))).one()
        return ImdWarningsOut(issued_at=newest[0], fetched_at=newest[1], districts_covered=0, districts=[])

    districts: dict[tuple[str, str], list[ImdWarningDayOut]] = {}
    seen: set[tuple[str, str]] = set()
    for r in rows:
        key = (r.state, r.district)
        seen.add(key)
        kinds = sorted({RAIN_KINDS[c] for c in map(int, r.codes.split(",")) if c in RAIN_KINDS}, key=SEVERITY.index)
        if kinds:
            districts.setdefault(key, []).append(ImdWarningDayOut(day=r.day, valid_date=r.valid_date, kinds=kinds, color=r.color))
    return ImdWarningsOut(
        issued_at=max(r.issued_at for r in rows),
        fetched_at=max(r.fetched_at for r in rows),
        districts_covered=len(seen),
        districts=[ImdWarningDistrictOut(state=s, district=d, days=days) for (s, d), days in districts.items()],
    )
