# AgriN Twin — Architecture

**Team VIDYUT** — Apratim Mitra (Lead), Sagnik Mitra, Dibyendu Chowdhury, Goutam Kumar Bose
**Track 4: AgriN & Regenerative Agricultural Intelligence** — Build with AI: Code for Communities, Second Edition (hack2skill)

## 1. The idea in one paragraph

Most agri-AI hackathon entries are a chatbot that gives farming tips.
AgriN Twin instead builds a **persistent digital twin per farm plot**
that fuses three independent data sources — satellite imagery, low-cost
IoT soil sensors, and farmer-submitted photos — into a single
**Regenerative Soil Health Trajectory score**, tracked over seasons
rather than optimized for this-season yield alone. Farmers reach it by
voice or text in their own language; national agri-research nodes across
BRICS share model improvements through a privacy-preserving exchange
that never touches raw farmer data.

## 2. System diagram (logical)

```
┌────────────────────────────────────────────────────────────────────┐
│                         FARMER-FACING CHANNELS                       │
│   IVR / phone call     WhatsApp        Web dashboard (this repo)     │
└───────────────┬───────────────┬───────────────────┬──────────────────┘
                │ STT (Bhashini/ │ webhook            │ HTTPS
                │  Whisper)      │                    │
                ▼               ▼                    ▼
        ┌──────────────────────────────────────────────────┐
        │            FastAPI backend  (backend/)             │
        │  ┌───────────┐ ┌───────────┐ ┌────────────────┐   │
        │  │ /plots     │ │ /voice    │ │ /federation     │   │
        │  │ (twin API) │ │ (agent)   │ │ (model exchange)│   │
        │  └─────┬─────┘ └─────┬─────┘ └────────┬────────┘   │
        │        │             │                │            │
        │  ┌─────▼─────────────▼────────────────▼─────────┐  │
        │  │              Service layer                    │  │
        │  │  satellite_service · disease_service ·         │  │
        │  │  soil_score_service · voice_agent_service ·    │  │
        │  │  federation_service                            │  │
        │  └─────┬─────────────────────────────┬───────────┘  │
        │        │                             │              │
        │  ┌─────▼──────┐              ┌───────▼────────┐     │
        │  │  SQL DB     │              │  CV model       │     │
        │  │ (Postgres   │              │  (MobileNetV2,  │     │
        │  │  in prod)   │              │   ml/training)  │     │
        │  └────────────┘              └────────────────┘     │
        └───────────┬──────────────────────────┬───────────────┘
                    │                          │
        ┌───────────▼─────────┐    ┌───────────▼─────────────┐
        │  Sentinel Hub /      │    │  ESP32 sensor pods        │
        │  Earth Engine API    │    │  (firmware/sensor_pod.ino)│
        │  (satellite NDVI)    │    │  soil moisture/temp,      │
        └──────────────────────┘    │  air temp/humidity,       │
                                     │  conductivity              │
                                     └────────────────────────────┘

        Cross-border layer:
        ┌──────────────────────────────────────────────────────┐
        │  FederationModelUpdate registry                        │
        │  IN-NODE-1 ──┐                                         │
        │  BR-NODE-1 ──┼── publish weight-delta URI + metrics    │
        │  ZA-NODE-1 ──┘   (never raw farmer data)                │
        └──────────────────────────────────────────────────────┘
```

## 3. Why this design

**Digital twin, not a Q&A bot.** Every plot accumulates a persistent
record (`Plot` → `SensorReading` / `SatelliteSnapshot` / `DiseaseReport`
/ `SoilHealthScore`, see `backend/app/models/domain.py`). This is what
lets the platform show a *trajectory* instead of a one-off answer — the
score trending 40 → 55 over two seasons is the actual regenerative-ag
story, and it's a data structure competitors built around a stateless
LLM prompt cannot easily produce.

**Graceful demo-mode fallbacks everywhere.** Satellite calls, the CV
model, and the LLM voice agent all have a production path (real
Sentinel Hub API, trained MobileNetV2, Anthropic API) *and* a
deterministic fallback that activates automatically when credentials or
trained weights aren't present (`SATELLITE_DEMO_MODE`,
`DISEASE_MODEL_DEMO_MODE`, empty `ANTHROPIC_API_KEY`). This means the
full pipeline is live-demoable on a judge's laptop with zero API keys,
while the code paths for a real production deployment are already
written and load automatically the moment credentials are added — judges
can inspect `app/services/*.py` to verify this isn't just mocked.

**Federation as a contract, not a claim.** Rather than asserting
"scalable across BRICS" in a slide, `FederationModelUpdate` is a real,
queryable table and API (`/api/v1/federation/*`) that three simulated
national nodes (India/Brazil/South Africa) actually publish to during
the demo — see `seed_demo_data.py`. It intentionally never carries raw
farmer data, only a pointer to a weight delta and an evaluation metric,
which is the actual mechanism that makes cross-border cooperation
legally/politically feasible for a Digital Public Good.

**One agent, three channels.** `voice_agent_service.handle_voice_query`
is channel-agnostic — the same grounded-response logic serves IVR,
WhatsApp, and the web dashboard's chat panel identically, matching the
brief's "voice, text, and messaging apps" requirement without three
separate implementations.

## 4. Production hardening checklist (beyond hackathon scope)

- Replace `Base.metadata.create_all` with Alembic migrations
- Swap SQLite for managed Postgres; add read replicas per region
- Real Sentinel Hub raster parsing (the OAuth/request flow is already
  implemented in `satellite_service.py`; only the GeoTIFF pixel-average
  step is stubbed)
- Train and ship real MobileNetV2 weights via `ml/training/train_disease_classifier.py`
  on PlantVillage + regionally-collected rice blast/bacterial blight images
- Per-device mTLS or rotating tokens for ESP32 pods instead of a shared API key
- A real federated-averaging orchestrator (Flower or TensorFlow Federated)
  behind the existing publish/pull API contract
- Bhashini ASR/TTS integration for the IVR channel (API contract already
  isolated behind the `transcript` field so this is a drop-in)
- Rate limiting, structured logging/observability, secrets management (Vault/KMS)
