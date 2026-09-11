"""
Regenerative Soil Health Trajectory scoring — the platform's core
differentiator versus "single season yield advisory" tools.

The score (0-100) blends three components:
  1. Vegetation vigor  — from satellite NDVI (canopy health / biomass proxy)
  2. Moisture stability — low variance in IoT soil-moisture readings over the
     trailing window indicates healthier water retention (a regenerative
     soil-structure signal), not just "high moisture"
  3. Crop diversity     — rotation/diversity history for the plot, since
     monocropping degrades soil over multi-season trajectories

Because it is computed repeatedly over time and stored, the *trend* is what
we surface most prominently on the dashboard — a farmer improving from 40
to 55 over two seasons is a much more actionable, and honest, signal than
a single absolute number.
"""
from statistics import pstdev

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.domain import DiseaseReport, Plot, SatelliteSnapshot, SensorReading, SoilHealthScore

MOISTURE_LOOKBACK = 10


def _vegetation_vigor_component(db: Session, plot_id: str) -> float:
    snap = (
        db.query(SatelliteSnapshot)
        .filter(SatelliteSnapshot.plot_id == plot_id)
        .order_by(desc(SatelliteSnapshot.captured_at))
        .first()
    )
    if not snap:
        return 50.0  # neutral default until first satellite pass
    # NDVI typically 0.2 (bare/stressed) to 0.8+ (dense healthy canopy) for cropland
    return max(0.0, min(100.0, (snap.ndvi - 0.1) / 0.7 * 100))


def _moisture_stability_component(db: Session, plot_id: str) -> float:
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.plot_id == plot_id)
        .order_by(desc(SensorReading.recorded_at))
        .limit(MOISTURE_LOOKBACK)
        .all()
    )
    if len(readings) < 2:
        return 50.0
    values = [r.soil_moisture_pct for r in readings]
    stdev = pstdev(values)
    # lower stdev -> higher score; stdev of 0 -> 100, stdev of 25+ -> near 0
    return max(0.0, min(100.0, 100 - (stdev / 25.0) * 100))


def _crop_diversity_component(db: Session, plot: Plot) -> float:
    """
    Simplified proxy: in production this reads a season-by-season crop
    history table and scores Shannon diversity across the last N seasons.
    For the current schema (single `primary_crop` field), we return a
    stable baseline plus a small bonus for known regenerative-friendly
    crops (legumes fix nitrogen and are commonly used as rotation crops).
    """
    legume_bonus_crops = {"lentil", "chickpea", "soybean", "groundnut", "beans"}
    base = 55.0
    if plot.primary_crop.lower() in legume_bonus_crops:
        base += 15.0
    return min(100.0, base)


def compute_and_store_score(db: Session, plot: Plot) -> SoilHealthScore:
    vigor = _vegetation_vigor_component(db, plot.id)
    moisture = _moisture_stability_component(db, plot.id)
    diversity = _crop_diversity_component(db, plot)

    score = round(0.45 * vigor + 0.35 * moisture + 0.20 * diversity, 2)

    previous = (
        db.query(SoilHealthScore)
        .filter(SoilHealthScore.plot_id == plot.id)
        .order_by(desc(SoilHealthScore.computed_at))
        .first()
    )
    trend = round(score - previous.score, 2) if previous else None

    record = SoilHealthScore(
        plot_id=plot.id,
        score=score,
        moisture_stability_component=round(moisture, 2),
        vegetation_vigor_component=round(vigor, 2),
        crop_diversity_component=round(diversity, 2),
        trend_vs_previous=trend,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def latest_disease_report(db: Session, plot_id: str) -> DiseaseReport | None:
    return (
        db.query(DiseaseReport)
        .filter(DiseaseReport.plot_id == plot_id)
        .order_by(desc(DiseaseReport.created_at))
        .first()
    )
