from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- Farmer & Plot ----------

class FarmerCreate(BaseModel):
    name: str
    phone_number: str
    preferred_language: str = "bn"
    nation: str = "IN"


class FarmerOut(FarmerCreate):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    created_at: datetime


class PlotCreate(BaseModel):
    farmer_id: str
    name: str
    latitude: float
    longitude: float
    area_hectares: float = 0.5
    primary_crop: str = "rice"
    nation: str = "IN"
    sensor_pod_id: str | None = None


class PlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    farmer_id: str
    name: str
    latitude: float
    longitude: float
    area_hectares: float
    primary_crop: str
    nation: str
    sensor_pod_id: str | None
    created_at: datetime


# ---------- IoT sensor ingestion ----------

class SensorReadingIn(BaseModel):
    """Payload shape sent by the ESP32 firmware over HTTPS POST."""
    plot_id: str
    soil_moisture_pct: float = Field(ge=0, le=100)
    soil_temp_c: float
    air_temp_c: float
    air_humidity_pct: float = Field(ge=0, le=100)
    soil_conductivity_us_cm: float
    battery_voltage: float | None = None


class SensorReadingOut(SensorReadingIn):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    recorded_at: datetime


# ---------- Satellite ----------

class SatelliteSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    plot_id: str
    ndvi: float
    ndmi: float | None
    land_surface_temp_c: float | None
    cloud_cover_pct: float | None
    source: str
    captured_at: datetime


# ---------- Disease diagnosis ----------

class DiseaseReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    plot_id: str
    predicted_label: str
    confidence: float
    is_healthy: bool
    recommended_action: str | None
    model_version: str
    created_at: datetime


# ---------- Soil health / regenerative trajectory ----------

class SoilHealthScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    plot_id: str
    score: float
    moisture_stability_component: float
    vegetation_vigor_component: float
    crop_diversity_component: float
    trend_vs_previous: float | None
    computed_at: datetime


class PlotTwinSummary(BaseModel):
    """The full 'digital twin' snapshot returned to the dashboard."""
    plot: PlotOut
    latest_sensor: SensorReadingOut | None
    latest_satellite: SatelliteSnapshotOut | None
    latest_disease_report: DiseaseReportOut | None
    latest_soil_score: SoilHealthScoreOut | None
    soil_score_history: list[SoilHealthScoreOut]


# ---------- Federation ----------

class FederationModelUpdateIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    node_id: str
    nation: str
    model_name: str
    model_version: str
    weight_delta_uri: str | None = None
    training_sample_count: float | None = None
    eval_metric_name: str | None = None
    eval_metric_value: float | None = None
    metadata_json: dict | None = None


class FederationModelUpdateOut(FederationModelUpdateIn):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    published_at: datetime


class FederationNodeStatus(BaseModel):
    node_id: str
    nation: str
    models_published: int
    latest_publish: datetime | None


# ---------- Voice agent ----------

class VoiceQueryIn(BaseModel):
    farmer_id: str | None = None
    plot_id: str | None = None
    language: str = "bn"
    transcript: str  # already speech-to-text'd upstream (Bhashini/Whisper)
    channel: str = "ivr"


class VoiceQueryOut(BaseModel):
    response_text: str
    intent: str
    session_id: str
