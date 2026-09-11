from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import Plot, SatelliteSnapshot
from app.schemas import schemas
from app.services import satellite_service

router = APIRouter(tags=["satellite"])


@router.post("/plots/{plot_id}/satellite/refresh", response_model=schemas.SatelliteSnapshotOut, status_code=201)
def refresh_satellite_snapshot(plot_id: str, db: Session = Depends(get_db)):
    """
    Triggers a fresh satellite pull for this plot. In production this
    would typically run on a scheduled job (e.g. every 5 days matching
    Sentinel-2 revisit time) rather than on-demand — exposed here as an
    endpoint for demo purposes so judges can see fresh data flow live.
    """
    plot = db.query(Plot).filter(Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(404, "Plot not found.")
    return satellite_service.fetch_and_store_snapshot(db, plot)


@router.get("/plots/{plot_id}/satellite", response_model=list[schemas.SatelliteSnapshotOut])
def list_satellite_snapshots(plot_id: str, limit: int = 30, db: Session = Depends(get_db)):
    return (
        db.query(SatelliteSnapshot)
        .filter(SatelliteSnapshot.plot_id == plot_id)
        .order_by(SatelliteSnapshot.captured_at.desc())
        .limit(limit)
        .all()
    )
