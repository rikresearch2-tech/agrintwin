import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import disease, federation, iot, plots, satellite, soil, voice
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.domain import Farmer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

# In production, use Alembic migrations instead of create_all.
# create_all is fine for the hackathon demo / first-run bootstrap.
Base.metadata.create_all(bind=engine)


def _seed_if_empty():
    """
    Auto-seeds demo data on startup if the database is empty. Matters for
    a live-URL deployment (Railway/Render/etc.): the first judge to open
    the dashboard shouldn't see an empty screen, and we can't rely on
    someone SSHing in to run seed_demo_data.py manually after deploy.
    A non-empty database (local dev after you've already seeded, or a
    redeploy with a persisted volume) is left untouched.
    """
    db = SessionLocal()
    try:
        if db.query(Farmer).first() is not None:
            return
        logger.info("Database is empty — auto-seeding demo data for first run.")
        from seed_demo_data import run as seed_run

        seed_run()
    except Exception as exc:  # noqa: BLE001 — never block app startup on seed failure
        logger.error("Auto-seed failed (app will still start): %s", exc)
    finally:
        db.close()


_seed_if_empty()

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AgriN Twin — a federated, regenerative-agriculture digital public good "
        "for BRICS nations. Fuses satellite imagery, IoT soil sensors, and "
        "computer-vision crop-disease diagnostics into a per-plot digital twin, "
        "delivered via voice, text, and messaging channels."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plots.router, prefix=settings.API_V1_PREFIX)
app.include_router(iot.router, prefix=settings.API_V1_PREFIX)
app.include_router(satellite.router, prefix=settings.API_V1_PREFIX)
app.include_router(disease.router, prefix=settings.API_V1_PREFIX)
app.include_router(soil.router, prefix=settings.API_V1_PREFIX)
app.include_router(federation.router, prefix=settings.API_V1_PREFIX)
app.include_router(voice.router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["health"])
def root():
    return {
        "service": settings.APP_NAME,
        "status": "ok",
        "env": settings.ENV,
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}
