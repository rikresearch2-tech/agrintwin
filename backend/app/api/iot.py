from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.domain import Plot, SensorReading
from app.schemas import schemas

router = APIRouter(tags=["iot-ingestion"])
settings = get_settings()


def verify_pod_key(x_pod_api_key: str = Header(...)):
    """
    Lightweight shared-key auth for ESP32 pods. Production hardening:
    replace with per-device mTLS certs or rotating tokens issued at
    device-provisioning time (see docs/ARCHITECTURE.md).
    """
    if x_pod_api_key != settings.IOT_INGEST_API_KEY:
        raise HTTPException(401, "Invalid sensor pod API key.")
    return True


@router.post("/sensor-readings", response_model=schemas.SensorReadingOut, status_code=201, dependencies=[Depends(verify_pod_key)])
def ingest_sensor_reading(payload: schemas.SensorReadingIn, db: Session = Depends(get_db)):
    plot = db.query(Plot).filter(Plot.id == payload.plot_id).first()
    if not plot:
        raise HTTPException(404, "Unknown plot_id — pod may be misconfigured.")

    reading = SensorReading(**payload.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/plots/{plot_id}/sensor-readings", response_model=list[schemas.SensorReadingOut])
def list_sensor_readings(plot_id: str, limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(SensorReading)
        .filter(SensorReading.plot_id == plot_id)
        .order_by(SensorReading.recorded_at.desc())
        .limit(limit)
        .all()
    )
