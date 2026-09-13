from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Zone
from app.schemas import CorridorOut

router = APIRouter(prefix="/corridors", tags=["corridors"])

_TIER_RANK = {"low": 0, "moderate": 1, "high": 2}


def _corridor_code(zone_name: str) -> str:
    """Zone names already carry the real OSM highway `ref` this project's own
    generate_zone_predictions.py embedded, e.g. 'NH310A (1224920841_00_000)'
    or 'road (595775891_00_020)' for an unnamed way -- no new data source,
    just grouping what's already stored."""
    return zone_name.split(" (")[0].strip() or "Unnamed"


@router.get("", response_model=list[CorridorOut])
def list_corridors(state: str | None = None, db: Session = Depends(get_db)):
    """Groups all zones by their real highway/road code and surfaces, per
    corridor: how many zones sit on it, its single highest-risk zone, and how
    many of its zones currently have an active alert. Nothing here is
    invented -- it's the same zones and alerts /zones and /alerts already
    serve, just aggregated by corridor instead of listed flat."""
    query = db.query(Zone)
    if state:
        query = query.filter(Zone.state == state)
    zones = query.all()
    active_zone_ids = {
        a.zone_id for a in db.query(Alert.zone_id).filter(Alert.status == "active").all()
    }

    groups: dict[str, list[Zone]] = defaultdict(list)
    for z in zones:
        groups[_corridor_code(z.name)].append(z)

    corridors = []
    for code, zs in groups.items():
        worst = max(zs, key=lambda z: _TIER_RANK.get(z.risk_tier, -1))
        active_count = sum(1 for z in zs if z.id in active_zone_ids)
        corridors.append(
            CorridorOut(
                code=code,
                zone_count=len(zs),
                active_alert_count=active_count,
                worst_risk_tier=worst.risk_tier,
                worst_zone_name=worst.name,
                worst_susceptibility_score=worst.susceptibility_score,
            )
        )

    corridors.sort(
        key=lambda c: (_TIER_RANK.get(c.worst_risk_tier, -1), c.active_alert_count),
        reverse=True,
    )
    return corridors
