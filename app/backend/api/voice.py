import asyncio
import base64
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import Response

from app.backend.dependencies import VoiceBackendDep
from app.backend.schemas import (
    VoiceInfoRead,
    VoiceSpeakRequest,
    VoiceStatusRead,
    VoiceTranscriptRead,
)
from app.core.config import cfg
from app.integrations.kitten import VoiceError, get_voice_backend

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _info_list(items: list) -> list[VoiceInfoRead]:
    return [
        VoiceInfoRead(name=v.name, title=v.title, kind=v.kind, language=v.language)
        for v in items
    ]


@router.get("/status", response_model=VoiceStatusRead)
async def voice_status(backend: VoiceBackendDep) -> VoiceStatusRead:
    data = await backend.status()
    return VoiceStatusRead(
        backend=data.backend,
        ready=data.ready,
        model=data.model,
        sample_rate=data.sample_rate,
        default_voice=data.default_voice,
        detail=data.detail,
        voices=_info_list(data.voices),
    )


@router.get("/voices", response_model=list[VoiceInfoRead])
async def list_voices(backend: VoiceBackendDep) -> list[VoiceInfoRead]:
    try:
        return _info_list(await backend.list_voices())
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/transcribe", response_model=VoiceTranscriptRead)
async def transcribe(
    backend: VoiceBackendDep,
    file: Annotated[UploadFile, File()],
    language: Annotated[str | None, Form()] = None,
) -> VoiceTranscriptRead:
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
    if len(audio) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл слишком большой (максимум 25 МБ)",
        )
    try:
        text = await backend.transcribe(audio, file.filename or "audio.wav", language)
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return VoiceTranscriptRead(text=text)


@router.post("/speak")
async def speak(payload: VoiceSpeakRequest, backend: VoiceBackendDep) -> Response:
    if not backend.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Голосовой движок не готов",
        )
    if len(payload.text) > cfg.kitten.max_input_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Слишком длинный текст (максимум {cfg.kitten.max_input_chars} символов)",
        )
    try:
        audio = await backend.synthesize(payload.text, payload.voice, payload.reference)
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    media_type = "audio/wav" if backend.name == "local" else "audio/mpeg"
    return Response(content=audio, media_type=media_type)


@router.post("/clone", response_model=VoiceInfoRead)
async def clone_voice(
    backend: VoiceBackendDep,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
) -> VoiceInfoRead:
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
    if len(audio) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл слишком большой (максимум 25 МБ)",
        )
    try:
        info = await backend.clone_voice(
            name.strip() or "voice", audio, file.filename or "reference.wav"
        )
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return VoiceInfoRead(name=info.name, title=info.title, kind=info.kind, language=info.language)


@router.websocket("/tts")
async def voice_tts(websocket: WebSocket) -> None:
    """Stream speech for text fragments as a persistent PCM channel.

    Client sends ``{"type": "speak", "text": ...}`` for each phrase; the server
    replies with ``{"type": "audio", "data": <base64 PCM16>}`` chunks followed by
    ``{"type": "done"}``. ``{"type": "cancel"}`` stops the current phrase (used for
    barge-in). This keeps the API key server-side and lets the browser play audio
    as it arrives.
    """
    await websocket.accept()
    backend = get_voice_backend()
    send_lock = asyncio.Lock()
    voice: str | None = cfg.kitten.voice
    reference: str | None = None

    async def send(payload: dict) -> None:
        async with send_lock:
            await websocket.send_json(payload)

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    cancel = asyncio.Event()

    async def worker() -> None:
        while True:
            text = await queue.get()
            if text is None:
                break
            cancel.clear()
            try:
                async for chunk in backend.synthesize_stream(text, voice, reference, "pcm"):
                    if cancel.is_set():
                        break
                    await send({"type": "audio", "data": base64.b64encode(chunk).decode("ascii")})
                await send({"type": "done"})
            except VoiceError as exc:
                await send({"type": "error", "detail": str(exc)})
            except Exception:  # noqa: BLE001 - keep the channel alive
                await send({"type": "error", "detail": "voice error"})

    await send(
        {
            "type": "ready",
            "backend": backend.name,
            "sample_rate": backend.sample_rate,
        }
    )
    worker_task = asyncio.create_task(worker())
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            kind = message.get("type")
            if kind == "config":
                voice = message.get("voice") or cfg.kitten.voice
                reference = message.get("reference") or None
            elif kind == "speak":
                text = str(message.get("text") or "").strip()
                if text:
                    await queue.put(text[: cfg.kitten.max_input_chars])
            elif kind == "cancel":
                cancel.set()
            elif kind == "ping":
                await send({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        cancel.set()
        await queue.put(None)
        worker_task.cancel()


__all__ = ["router"]
