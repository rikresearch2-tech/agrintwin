"""
Voice-first agronomy agent.

Flow in production: farmer calls an IVR number or messages WhatsApp in
their own language -> speech-to-text (Bhashini for Indian languages, or
Whisper for broader BRICS coverage) -> this service grounds the query in
the farmer's actual plot-twin data (never a generic LLM answer) -> text
response -> text-to-speech -> played back or sent as a voice note.

This module implements the grounding + reasoning step. STT/TTS are
pluggable upstream/downstream (see api/voice.py) so the same core agent
serves IVR, WhatsApp, and the web dashboard's chat panel identically —
one agent, three channels, matching the "aggregates via voice, text, and
messaging apps" requirement from the problem statement.

DEMO PATH: if ANTHROPIC_API_KEY is not set, falls back to a rule-based
intent classifier + templated response so the endpoint still works live
without requiring API credentials during judging.
"""
import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.domain import Plot, VoiceSession
from app.schemas.schemas import PlotTwinSummary

logger = logging.getLogger(__name__)
settings = get_settings()


# Multilingual keyword patterns — a minimal illustration of the
# "voice/text across diverse linguistic regions" requirement. Production
# NLU (Bhashini or an LLM call, see _llm_response below) replaces this
# entirely; this fallback exists only so the demo works offline/without
# API keys while still showing real regional-language coverage rather
# than English-only matching.
#
# Small-talk intents (greeting/thanks/farewell) are checked BEFORE the
# farm-data intents and do NOT fall through to the data dump — a rule-
# based fallback that answers "hello" with a wall of sensor readings is
# a worse demo than no fallback at all, since it's the first thing any
# judge tries.
INTENT_PATTERNS = {
    "greeting": r"^\s*(hi|hello|hey|namaste|salam"
                r"|nomoshkar|ei je"                      # Bengali: greetings
                r"|ola|oi)\b",                             # Portuguese: hello
    "thanks": r"\b(thanks|thank you|thx"
              r"|dhonnobad"                                # Bengali: thank you
              r"|obrigad)\b",                               # Portuguese: thank you (obrigado/a)
    "farewell": r"\b(bye|goodbye|see you"
                r"|bidae"                                    # Bengali: farewell
                r"|tchau|adeus)\b",                           # Portuguese: bye
    "disease_query": r"\b(disease|leaf|spot|blight|pest|rot|fungus"
                      r"|rog|poka|pata"                       # Bengali (romanized): disease, insect, leaf
                      r"|doenca|praga|folha"                  # Portuguese: disease, pest, leaf
                      r"|isifo|isinambuzane)\b",               # isiZulu: disease, pest
    "irrigation_query": r"\b(water|irrigat|moisture|dry|drought"
                         r"|jol|shech|khora"                   # Bengali: water, irrigation, dry
                         r"|agua|irriga|seca"                  # Portuguese: water, irrigate, drought
                         r"|amanzi|ukoma)\b",                   # isiZulu: water, dry
    "soil_health_query": r"\b(soil|health|score|fertiliz|nutrient"
                          r"|mati|sar"                          # Bengali: soil, fertilizer
                          r"|solo|fertiliz"                     # Portuguese: soil, fertilize
                          r"|inhlabathi)\b",                    # isiZulu: soil
    "weather_query": r"\b(weather|rain|forecast|temperature"
                      r"|briShTi|abohaoa"                       # Bengali: rain, weather
                      r"|chuva|tempo)\b",                        # Portuguese: rain, weather
    "general_advisory": r".*",
}

# Checked in this exact order: small talk first, or "hi, how's my soil"
# would still match "soil" and skip the greeting.
_INTENT_PRIORITY = [
    "greeting", "thanks", "farewell",
    "disease_query", "irrigation_query", "soil_health_query", "weather_query",
]


def _classify_intent(transcript: str) -> str:
    text = transcript.lower().strip()
    for intent in _INTENT_PRIORITY:
        if re.search(INTENT_PATTERNS[intent], text):
            return intent
    return "general_advisory"


def _build_grounded_context(twin: PlotTwinSummary | None) -> str:
    if not twin:
        return "No plot data is linked to this farmer yet."
    lines = [f"Plot: {twin.plot.name}, crop: {twin.plot.primary_crop}."]
    if twin.latest_soil_score:
        lines.append(
            f"Current regenerative soil score: {twin.latest_soil_score.score}/100 "
            f"(trend {twin.latest_soil_score.trend_vs_previous or 'n/a'})."
        )
    if twin.latest_satellite:
        lines.append(f"Latest satellite NDVI: {twin.latest_satellite.ndvi}.")
    if twin.latest_sensor:
        lines.append(f"Latest soil moisture: {twin.latest_sensor.soil_moisture_pct}%.")
    if twin.latest_disease_report:
        lines.append(
            f"Most recent disease scan: {twin.latest_disease_report.predicted_label} "
            f"(confidence {twin.latest_disease_report.confidence})."
        )
    return " ".join(lines)


def _rule_based_response(intent: str, twin: PlotTwinSummary | None, language: str) -> str:
    plot_name = twin.plot.name if twin else "your plot"
    context = _build_grounded_context(twin)

    # Small talk gets a short, natural reply — never the data dump. This
    # is what a farmer actually expects from "hello", and it's the first
    # thing anyone testing the agent tries.
    if intent == "greeting":
        return f"Hello! I'm your AgriN field agent for {plot_name}. Ask me about soil health, irrigation, disease, or weather."
    if intent == "thanks":
        return "You're welcome — let me know if you need anything else about your farm."
    if intent == "farewell":
        return "Take care. I'm here whenever you need farm advice."

    templates = {
        "disease_query": "Based on your last scan: {context} If symptoms are worsening, send a fresh photo for re-diagnosis.",
        "irrigation_query": "Based on your sensor data: {context} Consider irrigating if soil moisture is below 30%.",
        "soil_health_query": "Your soil health trajectory: {context} A rising trend means your regenerative practices are working.",
        "weather_query": "Weather forecasting integration is available in the full deployment — check satellite land-surface temperature trend: {context}",
    }
    if intent in templates:
        return templates[intent].format(context=context)

    # general_advisory: an unrecognized question. Rather than silently
    # dumping the full status block (which reads as a broken chatbot,
    # not an answer), ask what the person wants — this is the honest
    # behavior for a rule-based fallback that genuinely doesn't
    # understand the question. The real LLM path (_llm_response) doesn't
    # have this limitation and answers free-form questions directly.
    return (
        f"I didn't catch a specific question there. I can tell you about {plot_name}'s "
        "soil health, irrigation needs, disease status, or weather — what would you like to know?"
    )


def _agent_system_prompt(language: str) -> str:
    return (
        "You are an agronomy advisor for a smallholder farmer speaking a regional "
        "language. Answer ONLY using the farm data context provided — never invent "
        "readings. Keep the answer to 2-3 short sentences, in simple, plain language "
        f"suitable for a voice reply, in {language}."
    )


def _llm_response(transcript: str, intent: str, twin: PlotTwinSummary | None, language: str) -> str:
    """
    Calls Anthropic's API with the grounded plot-twin context. Kept as a
    thin, swappable function so the LangGraph orchestration layer (used
    in the full deployment for multi-turn memory + tool calls to trigger
    re-scans, schedule reminders, etc.) can wrap this same call.
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        context = _build_grounded_context(twin)
        message = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=200,
            system=_agent_system_prompt(language),
            messages=[
                {
                    "role": "user",
                    "content": f"Farm data context: {context}\n\nFarmer's question: {transcript}",
                }
            ],
        )
        return "".join(block.text for block in message.content if hasattr(block, "text"))
    except Exception as exc:  # noqa: BLE001 — never let a live demo crash on LLM/network failure
        # Logged (not silently swallowed) so a misconfigured/expired/rate-
        # limited key is visible in the server console instead of looking
        # identical to "no key configured" — this was a real debugging
        # blind spot during development.
        logger.warning("Anthropic call failed, falling back to rule-based response: %s", exc)
        return _rule_based_response(intent, twin, language)


def _gemini_response(transcript: str, intent: str, twin: PlotTwinSummary | None, language: str) -> str:
    """
    Free-tier alternative to _llm_response, using Google AI Studio's
    Gemini API — unlike Anthropic's one-time trial credit, Gemini's API
    free tier is permanent and requires no credit card, which matters for
    a team running this on a hackathon budget. Same grounding contract as
    _llm_response: answer only from the supplied farm-data context.
    Requires `pip install google-genai`.
    """
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        context = _build_grounded_context(twin)

        # NOTE: we previously tried thinking_config=ThinkingConfig(thinking_budget=0)
        # to stop gemini-3.6-flash's internal "thinking" from eating the
        # output token budget (which was truncating replies mid-word).
        # That parameter got rejected outright with a 400 INVALID_ARGUMENT
        # by the API for this model, so instead we solve the same problem
        # with a generous max_output_tokens ceiling — thinking tokens can
        # eat into this, but 2000 tokens leaves enough headroom that a
        # short 2-3 sentence farm-advice reply is never cut off, without
        # depending on a parameter this model rejects.
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Farm data context: {context}\n\nFarmer's question: {transcript}",
            config=types.GenerateContentConfig(
                system_instruction=_agent_system_prompt(language),
                max_output_tokens=2000,
            ),
        )
        text = response.text
        if not text or not text.strip():
            logger.warning("Gemini returned an empty response, falling back to rule-based response.")
            return _rule_based_response(intent, twin, language)
        return text
    except Exception as exc:  # noqa: BLE001 — never let a live demo crash on LLM/network failure
        logger.warning("Gemini call failed, falling back to rule-based response: %s", exc)
        return _rule_based_response(intent, twin, language)


def handle_voice_query(
    db: Session,
    transcript: str,
    language: str,
    farmer_id: str | None,
    twin: PlotTwinSummary | None,
    channel: str = "ivr",
) -> dict:
    intent = _classify_intent(transcript)

    # Provider priority: Anthropic (if configured) -> Gemini free tier (if
    # configured) -> rule-based fallback. Small talk (greeting/thanks/
    # farewell) always uses the rule-based reply even when an LLM is
    # configured — it's cheaper, instant, and an LLM call adds nothing
    # for "hello".
    if intent in ("greeting", "thanks", "farewell"):
        response_text = _rule_based_response(intent, twin, language)
    elif settings.ANTHROPIC_API_KEY:
        response_text = _llm_response(transcript, intent, twin, language)
    elif settings.GEMINI_API_KEY:
        response_text = _gemini_response(transcript, intent, twin, language)
    else:
        logger.info("No ANTHROPIC_API_KEY or GEMINI_API_KEY set — using rule-based fallback.")
        response_text = _rule_based_response(intent, twin, language)

    session = VoiceSession(
        id=str(uuid.uuid4()),
        farmer_id=farmer_id,
        channel=channel,
        language=language,
        transcript=transcript,
        intent=intent,
        response_text=response_text,
    )
    db.add(session)
    db.commit()

    return {"response_text": response_text, "intent": intent, "session_id": session.id}
