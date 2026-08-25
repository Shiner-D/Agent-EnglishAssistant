"""TTS (Text-to-Speech) API using edge-tts."""
import io
import asyncio
import edge_tts
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

VOICES = {
    "en-US": "en-US-JennyNeural",   # American English (female)
    "en-GB": "en-GB-SoniaNeural",   # British English (female)
    "en-US-male": "en-US-GuyNeural",
    "en-GB-male": "en-GB-RyanNeural",
}


@router.get("/speak")
async def speak(
    text: str = Query(...),
    voice: str = Query("en-US"),
    rate: str = Query("+0%"),
):
    """Generate TTS audio and stream it back."""
    voice_name = VOICES.get(voice, VOICES["en-US"])

    async def audio_generator():
        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="tts.mp3"'},
    )


@router.get("/voices")
async def list_voices():
    return {"voices": list(VOICES.keys())}
