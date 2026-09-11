from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import DiseaseReport, Farmer, Plot, SatelliteSnapshot, SensorReading, SoilHealthScore
from app.schemas import schemas

router = APIRouter(tags=["farmers-and-plots"])


@router.post("/farmers", response_model=schemas.FarmerOut, status_code=201)
def create_farmer(payload: schemas.FarmerCreate, db: Session = Depends(get_db)):
    existing = db.query(Farmer).filter(Farmer.phone_number == payload.phone_number).first()
    if existing:
        raise HTTPException(409, "A farmer with this phone number is already registered.")
    farmer = Farmer(**payload.model_dump())
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return farmer


@router.get("/farmers/{farmer_id}", response_model=schemas.FarmerOut)
def get_farmer(farmer_id: str, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(404, "Farmer not found.")
    return farmer


@router.post("/plots", response_model=schemas.PlotOut, status_code=201)
def create_plot(payload: schemas.PlotCreate, db: Session = Depends(get_db)):
    farmer = db.query(Farmer).filter(Farmer.id == payload.farmer_id).first()
    if not farmer:
        raise HTTPException(404, "Farmer not found — create the farmer first.")
    plot = Plot(**payload.model_dump())
    db.add(plot)
    db.commit()
    db.refresh(plot)
    return plot


@router.get("/plots", response_model=list[schemas.PlotOut])
def list_plots(db: Session = Depends(get_db)):
    return db.query(Plot).all()


@router.get("/plots/{plot_id}", response_model=schemas.PlotOut)
def get_plot(plot_id: str, db: Session = Depends(get_db)):
    plot = db.query(Plot).filter(Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(404, "Plot not found.")
    return plot


@router.get("/plots/{plot_id}/twin", response_model=schemas.PlotTwinSummary)
def get_plot_twin(plot_id: str, db: Session = Depends(get_db)):
    """The core 'digital twin' view — everything known about a plot, fused."""
    plot = db.query(Plot).filter(Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(404, "Plot not found.")

    latest_sensor = (
        db.query(SensorReading)
        .filter(SensorReading.plot_id == plot_id)
        .order_by(SensorReading.recorded_at.desc())
        .first()
    )
    latest_satellite = (
        db.query(SatelliteSnapshot)
        .filter(SatelliteSnapshot.plot_id == plot_id)
        .order_by(SatelliteSnapshot.captured_at.desc())
        .first()
    )
    latest_disease = (
        db.query(DiseaseReport)
        .filter(DiseaseReport.plot_id == plot_id)
        .order_by(DiseaseReport.created_at.desc())
        .first()
    )
    score_history = (
        db.query(SoilHealthScore)
        .filter(SoilHealthScore.plot_id == plot_id)
        .order_by(SoilHealthScore.computed_at.desc())
        .limit(20)
        .all()
    )
    latest_score = score_history[0] if score_history else None

    return schemas.PlotTwinSummary(
        plot=plot,
        latest_sensor=latest_sensor,
        latest_satellite=latest_satellite,
        latest_disease_report=latest_disease,
        latest_soil_score=latest_score,
        soil_score_history=list(reversed(score_history)),
    )
