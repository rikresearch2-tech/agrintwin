from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import Plot, SoilHealthScore
from app.schemas import schemas
from app.services import soil_score_service

router = APIRouter(tags=["soil-health"])


@router.post("/plots/{plot_id}/soil-score/compute", response_model=schemas.SoilHealthScoreOut, status_code=201)
def compute_soil_score(plot_id: str, db: Session = Depends(get_db)):
    plot = db.query(Plot).filter(Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(404, "Plot not found.")
    return soil_score_service.compute_and_store_score(db, plot)


@router.get("/plots/{plot_id}/soil-score/history", response_model=list[schemas.SoilHealthScoreOut])
def soil_score_history(plot_id: str, limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(SoilHealthScore)
        .filter(SoilHealthScore.plot_id == plot_id)
        .order_by(SoilHealthScore.computed_at.desc())
        .limit(limit)
        .all()
    )
