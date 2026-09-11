# AgriN Twin

**A federated, regenerative-agriculture digital public good for BRICS nations.**

Built by **Team VIDYUT** (Apratim Mitra — Team Lead, Dibyendu
Chowdhury, Goutam Kumar Bose) for **Track 4: AgriN & Regenerative
Agricultural Intelligence** at *Build with AI: Code for Communities —
Second Edition* (hack2skill).

## What it is

Instead of another crop-advisory chatbot, AgriN Twin builds a
**persistent digital twin for every farm plot**, fusing:

1. **Satellite imagery** (Sentinel-2 NDVI/NDMI) — vegetation vigor
2. **Low-cost ESP32 IoT sensor pods** (~₹500/pod) — soil moisture, temp, conductivity
3. **Farmer-submitted photos** — CV-based crop disease diagnosis

...into a **Regenerative Soil Health Trajectory score** tracked over
seasons, not just this season's yield. Farmers reach the platform by
voice, WhatsApp, or web, in their own language. National research nodes
across BRICS share model improvements through a federated exchange that
never touches raw farmer data — a real, working demonstration of the
"digital public good" and "cross-border cooperation" requirements in the
problem statement, not just a claim on a slide.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design
rationale and system diagram.

## Repository layout

```
backend/    FastAPI service — the digital twin API, all business logic
frontend/   React + Vite dashboard ("Field Ledger" design)
firmware/   ESP32 sensor pod firmware (Arduino/C++) + wiring + BOM
ml/         CV disease-classifier training pipeline (MobileNetV2)
docs/       Architecture notes
```

## Quickstart (judging demo — no API keys required)

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
python seed_demo_data.py        # seeds 3 farmers across India/Brazil/South Africa
uvicorn app.main:app --reload   # http://localhost:8000/docs for interactive API

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Everything works out of the box in **demo mode**: synthetic-but-realistic
satellite data, a heuristic crop-disease classifier, and a rule-based
multilingual voice agent all activate automatically with zero external
API keys. Every one of those has a fully-implemented production path
(real Sentinel Hub calls, a trainable MobileNetV2 classifier, an
Anthropic-LLM-grounded agent) — see `docs/ARCHITECTURE.md` §4 for how to
switch each one on.

## Tests

```bash
cd backend
pytest -v
```

## What's real vs. what's demo-mode

| Component | Status | Notes |
|---|---|---|
| Disease diagnosis | **Real trained CNN, bundled** (`app/ml/weights/disease_model.keras`) | Trained from scratch (no ImageNet transfer learning — that weights host wasn't reachable from the training environment) on ~1,600 real PlantVillage images, 5 classes. 75.9% validation accuracy. **Does not cover rice diseases** — PlantVillage has no rice-disease images; rice photos still get a prediction but it's not a real diagnosis. See caveat below. |
| Satellite NDVI | Seeded synthetic time series (demo mode) | Sentinel Hub OAuth + Processing API is fully implemented (`satellite_service.py`) but needs paid API credentials to activate |
| Voice agent | Rule-based multilingual intent matching (demo mode) | Anthropic Claude or Google Gemini integration is implemented and grounds responses in live twin data — activates automatically once `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` is set (Anthropic takes priority if both are set; Gemini's free tier needs no credit card, see `backend/.env.example`) |
| Federation | 3 simulated node publishes | Same API contract works for any real national node |

**Disease-model caveat, stated plainly for judges:** the bundled model was trained only on classes with real, labeled, publicly-available images we could source in the hackathon window (healthy/maize_leaf_spot/potato_late_blight/tomato_early_blight/tomato_leaf_curl_virus). It has never seen a rice disease image. Rather than let it guess on tissue it's never seen — it originally mislabeled a real rice blast photo "healthy" at 98% confidence during our own testing — `disease_service.diagnose()` routes by the plot's crop: photos from tomato/potato/maize plots go to the trained CNN, everything else (rice included) goes to the HSV lesion-detection heuristic instead. The `model_version` field on every response says which path served that prediction, so this is never silently presented as a working rice diagnosis. Closing the gap for real needs a labeled rice-disease dataset (Kaggle and Mendeley both host relevant ones) — tracked in `docs/ARCHITECTURE.md`.
