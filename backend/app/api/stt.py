import asyncio
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger

router = APIRouter()

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper small model (first run downloads ~150MB)...")
        _model = WhisperModel("small", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _model


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    suffix = ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        def _run():
            model = _get_model()
            segments, _ = model.transcribe(
                tmp_path,
                language="zh",
                beam_size=1,
                initial_prompt="以下是普通话的句子，使用简体中文。",
                vad_filter=True,
                condition_on_previous_text=False,
            )
            return "".join(s.text for s in segments).strip()

        transcript = await asyncio.to_thread(_run)
        logger.info(f"STT transcript: {transcript!r}")
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)
