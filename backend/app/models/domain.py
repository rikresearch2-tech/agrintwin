"""
Core domain models for AgriN Twin.

Design note: every plot is a "digital twin" — a persistent entity that
accumulates satellite observations, IoT sensor readings, disease reports,
and derived soil-health-trajectory scores over time. This is the central
data structure the whole platform is built around.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BRICSNation(str, enum.Enum):
    INDIA = "IN"
    BRAZIL = "BR"
    RUSSIA = "RU"
    CHINA = "CN"
    SOUTH_AFRICA = "ZA"
    EGYPT = "EG"
    ETHIOPIA = "ET"
    IRAN = "IR"
    UAE = "AE"


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    preferred_language = Column(String, default="bn")  # ISO 639-1: bn, hi, en, pt, sw...
    nation = Column(Enum(BRICSNation), default=BRICSNation.INDIA)
    created_at = Column(DateTime, default=_now)

    plots = relationship("Plot", back_populates="farmer", cascade="all, delete-orphan")


class Plot(Base):
    """A single farm plot — the unit that the 'digital twin' is built around."""

    __tablename__ = "plots"

    id = Column(String, primary_key=True, default=_uuid)
    farmer_id = Column(String, ForeignKey("farmers.id"), nullable=False)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_hectares = Column(Float, default=0.5)
    primary_crop = Column(String, default="rice")
    nation = Column(Enum(BRICSNation), default=BRICSNation.INDIA)
    sensor_pod_id = Column(String, nullable=True, index=True)  # links to ESP32 device
    created_at = Column(DateTime, default=_now)

    farmer = relationship("Farmer", back_populates="plots")
    sensor_readings = relationship("SensorReading", back_populates="plot", cascade="all, delete-orphan")
    satellite_snapshots = relationship("SatelliteSnapshot", back_populates="plot", cascade="all, delete-orphan")
    disease_reports = relationship("DiseaseReport", back_populates="plot", cascade="all, delete-orphan")
    soil_scores = relationship("SoilHealthScore", back_populates="plot", cascade="all, delete-orphan")


class SensorReading(Base):
    """A single telemetry packet from an ESP32 sensor pod."""

    __tablename__ = "sensor_readings"

    id = Column(String, primary_key=True, default=_uuid)
    plot_id = Column(String, ForeignKey("plots.id"), nullable=False, index=True)
    soil_moisture_pct = Column(Float)
    soil_temp_c = Column(Float)
    air_temp_c = Column(Float)
    air_humidity_pct = Column(Float)
    soil_conductivity_us_cm = Column(Float)  # proxy for nutrient/salinity levels
    battery_voltage = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=_now)

    plot = relationship("Plot", back_populates="sensor_readings")


class SatelliteSnapshot(Base):
    """A derived satellite observation for a plot (from Sentinel-2 / Earth Engine)."""

    __tablename__ = "satellite_snapshots"

    id = Column(String, primary_key=True, default=_uuid)
    plot_id = Column(String, ForeignKey("plots.id"), nullable=False, index=True)
    ndvi = Column(Float)  # Normalized Difference Vegetation Index (-1 to 1)
    ndmi = Column(Float, nullable=True)  # Normalized Difference Moisture Index
    land_surface_temp_c = Column(Float, nullable=True)
    cloud_cover_pct = Column(Float, nullable=True)
    source = Column(String, default="sentinel-2")
    captured_at = Column(DateTime, default=_now)

    plot = relationship("Plot", back_populates="satellite_snapshots")


class DiseaseReport(Base):
    """Output of the CV crop-disease diagnostic pipeline."""

    __tablename__ = "disease_reports"

    id = Column(String, primary_key=True, default=_uuid)
    plot_id = Column(String, ForeignKey("plots.id"), nullable=False, index=True)
    image_path = Column(String, nullable=True)
    predicted_label = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    is_healthy = Column(Boolean, default=False)
    recommended_action = Column(Text, nullable=True)
    model_version = Column(String, default="v0.1-demo")
    created_at = Column(DateTime, default=_now)

    plot = relationship("Plot", back_populates="disease_reports")


class SoilHealthScore(Base):
    """
    The 'Regenerative Trajectory Score' — the core differentiator of this
    platform. Computed periodically from satellite + IoT + crop-rotation
    history, trending over time rather than a single-season yield number.
    """

    __tablename__ = "soil_health_scores"

    id = Column(String, primary_key=True, default=_uuid)
    plot_id = Column(String, ForeignKey("plots.id"), nullable=False, index=True)
    score = Column(Float, nullable=False)  # 0-100
    moisture_stability_component = Column(Float)
    vegetation_vigor_component = Column(Float)
    crop_diversity_component = Column(Float)
    trend_vs_previous = Column(Float, nullable=True)  # delta vs last score
    computed_at = Column(DateTime, default=_now)

    plot = relationship("Plot", back_populates="soil_scores")


class FederationModelUpdate(Base):
    """
    A privacy-preserving model-exchange record: nations publish only
    aggregated model deltas/embeddings here, never raw farmer data —
    this is what makes the platform a genuine cross-BRICS digital public good.
    """

    __tablename__ = "federation_model_updates"

    id = Column(String, primary_key=True, default=_uuid)
    node_id = Column(String, nullable=False, index=True)
    nation = Column(Enum(BRICSNation), nullable=False)
    model_name = Column(String, nullable=False)  # e.g. "disease-classifier", "soil-score-regressor"
    model_version = Column(String, nullable=False)
    weight_delta_uri = Column(String, nullable=True)  # pointer to object storage, never raw data
    training_sample_count = Column(Float, nullable=True)  # count only, not the data itself
    eval_metric_name = Column(String, nullable=True)
    eval_metric_value = Column(Float, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    published_at = Column(DateTime, default=_now)


class VoiceSession(Base):
    """Log of a voice/IVR interaction — for audit + continuous improvement."""

    __tablename__ = "voice_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    farmer_id = Column(String, ForeignKey("farmers.id"), nullable=True)
    channel = Column(String, default="ivr")  # ivr | whatsapp | web
    language = Column(String, default="bn")
    transcript = Column(Text, nullable=True)
    intent = Column(String, nullable=True)
    response_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
