# AgriN Twin — Backend

FastAPI service implementing the digital-twin API, satellite/IoT/CV
fusion, soil-health scoring, the federated BRICS model-exchange
registry, and the multilingual voice agent.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python seed_demo_data.py
uvicorn app.main:app --reload
```

Interactive API docs: `http://localhost:8000/docs`

## Project layout

```
app/
  main.py              FastAPI app + router wiring
  core/config.py        Settings (env-driven, all demo-mode flags live here)
  core/database.py      SQLAlchemy engine/session
  models/domain.py      ORM models — Farmer, Plot, SensorReading,
                         SatelliteSnapshot, DiseaseReport, SoilHealthScore,
                         FederationModelUpdate, VoiceSession
  schemas/schemas.py    Pydantic request/response schemas
  services/             Business logic, one module per concern:
    satellite_service.py    Sentinel Hub integration + synthetic fallback
    disease_service.py      CV inference (Keras model or heuristic fallback)
    soil_score_service.py   Regenerative trajectory scoring
    federation_service.py   Model-exchange registry
    voice_agent_service.py  Multilingual grounded agent (LLM or rule-based)
  api/                 One router per resource (plots, iot, satellite,
                        disease, soil, federation, voice)
tests/test_api.py       Full-lifecycle integration tests
seed_demo_data.py       3-nation demo dataset for judging
```

## Configuration

All configuration is environment-driven (`app/core/config.py`,
`.env.example`). Nothing needs to change to run the demo — every
external integration (satellite API, trained CV weights, LLM) falls
back to a deterministic demo mode when its credentials/weights are
absent. See the module docstrings in `app/services/` for the exact
fallback behavior of each.

## Docker

```bash
docker build -t agrin-twin-backend .
docker run -p 8000:8000 --env-file .env agrin-twin-backend
```
