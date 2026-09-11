"""
Federated model-exchange registry — the BRICS-cooperation layer.

Design principle (critical for the "digital public good" story): nodes
NEVER exchange raw farmer data. Each national/regional node trains its
disease-classifier or soil-scoring model locally on its own data, then
publishes only:
  - a pointer (URI) to the serialized weight delta / embedding update
  - the training sample COUNT (not the data)
  - an evaluation metric for transparency/trust scoring

This registry is intentionally simple (a Postgres/SQLite table behind a
REST API) rather than a full federated-averaging orchestration engine —
that's a reasonable production next step (e.g. Flower framework, or
TensorFlow Federated) but out of scope to fully implement in a hackathon
timeframe. What's demoed here is the *interoperability contract*: any
BRICS national node can publish/pull updates through one shared schema,
which is the actual blocker the problem statement describes.
"""
from collections import defaultdict

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.domain import FederationModelUpdate


def publish_update(db: Session, payload: dict) -> FederationModelUpdate:
    record = FederationModelUpdate(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_updates(db: Session, model_name: str | None = None, limit: int = 50) -> list[FederationModelUpdate]:
    q = db.query(FederationModelUpdate)
    if model_name:
        q = q.filter(FederationModelUpdate.model_name == model_name)
    return q.order_by(desc(FederationModelUpdate.published_at)).limit(limit).all()


def node_status(db: Session) -> list[dict]:
    updates = db.query(FederationModelUpdate).all()
    grouped: dict[str, dict] = defaultdict(lambda: {"count": 0, "latest": None, "nation": None})
    for u in updates:
        g = grouped[u.node_id]
        g["count"] += 1
        g["nation"] = u.nation
        if g["latest"] is None or u.published_at > g["latest"]:
            g["latest"] = u.published_at
    return [
        {
            "node_id": node_id,
            "nation": data["nation"],
            "models_published": data["count"],
            "latest_publish": data["latest"],
        }
        for node_id, data in grouped.items()
    ]
