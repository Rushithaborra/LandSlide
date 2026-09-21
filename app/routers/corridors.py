from fastapi import APIRouter, Depends
from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Zone
from app.schemas import CorridorOut

router = APIRouter(prefix="/corridors", tags=["corridors"])

# Zone names already carry the real OSM highway `ref` this project's own
# generate_zone_predictions.py embedded, e.g. 'NH310A (1224920841_00_000)' or
# 'road (595775891_00_020)' for an unnamed way -- no new data source, just
# grouping what's already stored. Done in SQL so the grouping covers every
# zone, not just a capped page: this endpoint used to fetch the top 5000
# zones and group them in Python, which silently undercounted any state
# larger than that (Meghalaya's 10,691 zones showed as 5,000) and could drop
# a road whose zones all ranked low.
#
# Cleaned up for Assam, where the raw grouping was misleading:
#  - the same highway appears under variant spellings ('NH27', 'NH 27', 'NH-27'),
#    so highway codes are normalised (upper-case, no spaces or hyphens) to one corridor;
#  - 58% of Assam's zones sit on unnamed OSM ways ('road'), which is not a corridor at
#    all, so those are labelled kind='unnamed' and the dashboard shows them as a count,
#    not as a road;
#  - real highways (NH/SH/AH) are told apart from local named roads (kind).
_RAW = func.coalesce(func.nullif(func.btrim(func.split_part(Zone.name, " (", 1)), ""), "Unnamed")
_IS_HIGHWAY = _RAW.op("~*")(r"^(NH|SH|AH)\s*-?\s*[0-9]")
_CODE = case((_IS_HIGHWAY, func.upper(func.regexp_replace(_RAW, r"[\s-]", "", "g"))), else_=_RAW)
_KIND = case((_IS_HIGHWAY, "highway"), (_RAW.in_(["road", "Unnamed"]), "unnamed"), else_="named")
_TIER_RANK = case((Zone.risk_tier == "high", 2), (Zone.risk_tier == "moderate", 1), (Zone.risk_tier == "low", 0), else_=-1)


def display_code(code: str) -> str:
    """'SH37;SH022' (OSM lists two refs for a road that has both a national-style and a
    state number) reads better as 'SH37 / SH022'."""
    return code.replace(";", " / ")


@router.get("", response_model=list[CorridorOut])
def list_corridors(state: str | None = None, db: Session = Depends(get_db)):
    """Groups all zones by their real highway/road code and surfaces, per
    corridor: how many zones sit on it, its single highest-risk zone, and how
    many of its zones currently have an active alert. Nothing here is
    invented -- it's the same zones and alerts /zones and /alerts already
    serve, just aggregated by corridor instead of listed flat."""
    has_active_alert = exists().where(Alert.zone_id == Zone.id, Alert.status == "active")
    ranked = select(
        _CODE.label("code"),
        _KIND.label("kind"),
        Zone.name,
        Zone.risk_tier,
        Zone.susceptibility_score,
        _TIER_RANK.label("tier_rank"),
        func.count().over(partition_by=_CODE).label("zone_count"),
        func.sum(case((has_active_alert, 1), else_=0)).over(partition_by=_CODE).label("active_alert_count"),
        # The corridor's worst zone: highest tier, then highest score.
        func.row_number()
        .over(
            partition_by=_CODE,
            order_by=(_TIER_RANK.desc(), Zone.susceptibility_score.desc().nulls_last(), Zone.id),
        )
        .label("rn"),
    )
    if state:
        ranked = ranked.where(Zone.state == state)
    ranked = ranked.subquery()

    rows = db.execute(
        select(ranked).where(ranked.c.rn == 1).order_by(ranked.c.tier_rank.desc(), ranked.c.active_alert_count.desc(), ranked.c.code)
    ).all()
    return [
        CorridorOut(
            code=display_code(r.code),
            kind=r.kind,
            zone_count=r.zone_count,
            active_alert_count=int(r.active_alert_count),
            worst_risk_tier=r.risk_tier,
            worst_zone_name=r.name,
            worst_susceptibility_score=r.susceptibility_score,
        )
        for r in rows
    ]
