from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import alerts, authority_contacts, corridors, rainfall, reports, surroundings, zones
from app.security import auth_enabled

app = FastAPI(title="Landslide Early Warning System — Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon prototype — tighten before any real deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zones.router)
app.include_router(surroundings.router)
app.include_router(rainfall.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(corridors.router)
app.include_router(authority_contacts.router)
# Citizen-report photos are stored in Supabase Storage (app/routers/reports.py),
# not served from this app -- no local /uploads mount needed.


@app.get("/health")
def health():
    return {"status": "ok", "officer_auth": "enabled" if auth_enabled() else "disabled"}
