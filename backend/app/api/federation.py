from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import schemas
from app.services import federation_service

router = APIRouter(tags=["federation"])


@router.post("/federation/updates", response_model=schemas.FederationModelUpdateOut, status_code=201)
def publish_model_update(payload: schemas.FederationModelUpdateIn, db: Session = Depends(get_db)):
    """
    Called by each national node's training pipeline after a local
    fine-tuning run. Only the weight-delta URI + aggregate metrics are
    sent — never raw farmer data — satisfying cross-border data
    sovereignty requirements while still enabling shared model improvement.
    """
    return federation_service.publish_update(db, payload.model_dump())


@router.get("/federation/updates", response_model=list[schemas.FederationModelUpdateOut])
def list_model_updates(model_name: str | None = None, db: Session = Depends(get_db)):
    return federation_service.list_updates(db, model_name)


@router.get("/federation/nodes", response_model=list[schemas.FederationNodeStatus])
def federation_node_status(db: Session = Depends(get_db)):
    return federation_service.node_status(db)
