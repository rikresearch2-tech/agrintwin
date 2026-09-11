from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.plots import get_plot_twin
from app.core.database import get_db
from app.schemas import schemas
from app.services import voice_agent_service

router = APIRouter(tags=["voice-agent"])


@router.post("/voice/query", response_model=schemas.VoiceQueryOut)
def voice_query(payload: schemas.VoiceQueryIn, db: Session = Depends(get_db)):
    """
    Single entry point for all conversational channels (IVR, WhatsApp,
    web chat widget). `transcript` is expected to already be speech-to-text
    output when coming from a voice channel — STT is handled upstream by
    the telephony/WhatsApp gateway (e.g. Bhashini ASR for Indian languages,
    Twilio + Whisper for broader reach) so this endpoint stays channel-agnostic.
    """
    twin = None
    if payload.plot_id:
        twin = get_plot_twin(payload.plot_id, db)

    result = voice_agent_service.handle_voice_query(
        db=db,
        transcript=payload.transcript,
        language=payload.language,
        farmer_id=payload.farmer_id,
        twin=twin,
        channel=payload.channel,
    )
    return result
