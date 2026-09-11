import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import DiseaseReport, Plot
from app.schemas import schemas
from app.services import disease_service

router = APIRouter(tags=["disease-diagnosis"])

UPLOAD_DIR = Path("uploads/disease_images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/plots/{plot_id}/disease-scan", response_model=schemas.DiseaseReportOut, status_code=201)
async def scan_crop_image(plot_id: str, image: UploadFile, db: Session = Depends(get_db)):
    plot = db.query(Plot).filter(Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(404, "Plot not found.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(400, "Empty image upload.")

    result = disease_service.diagnose(image_bytes, crop=plot.primary_crop)

    filename = f"{uuid.uuid4()}_{image.filename or 'scan.jpg'}"
    image_path = UPLOAD_DIR / filename
    image_path.write_bytes(image_bytes)

    report = DiseaseReport(
        plot_id=plot_id,
        image_path=str(image_path),
        **result,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/plots/{plot_id}/disease-reports", response_model=list[schemas.DiseaseReportOut])
def list_disease_reports(plot_id: str, limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(DiseaseReport)
        .filter(DiseaseReport.plot_id == plot_id)
        .order_by(DiseaseReport.created_at.desc())
        .limit(limit)
        .all()
    )
