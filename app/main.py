import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import alerts, rainfall, reports, zones

app = FastAPI(title="Landslide Early Warning System — Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon prototype — tighten before any real deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zones.router)
app.include_router(rainfall.router)
app.include_router(alerts.router)
app.include_router(reports.router)

pathlib.Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health")
def health():
    return {"status": "ok"}
