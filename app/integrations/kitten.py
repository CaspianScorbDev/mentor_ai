"""Speech synthesis and transcription on top of KittenTTS 2.

Two interchangeable engines sit behind one interface:

* ``local`` — the ``kittenml`` Python package runs ``KittenML/kitten-tts-2`` on
  this machine (torch, MPS/CUDA/CPU) with built-in voices, voice cloning and a
  Whisper transcriber. No API key, no network at inference time.
* ``hosted`` — the KittenML HTTP/WebSocket API (``api.kittenml.com``) with 177
  voices, 20 languages, emotion tags and voice cloning. Requires an API key,
  which must stay server-side.

The local backend imports torch/transformers lazily so a hosted-only install
never pays for them.
"""

import asyncio
import io
import json
import pathlib
import re
import tempfile
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

import httpx

from app.core.config import KittenSettings, cfg


class VoiceError(RuntimeError):
    """Raised when a speech or transcription operation fails."""


@dataclass(slots=True)
class VoiceInfo:
    name: str
    title: str
    kind: Literal["builtin", "cloned"] = "builtin"
    language: str | None = None


@dataclass(slots=True)
class VoiceStatus:
    backend: str
    ready: bool
    model: str
    sample_rate: int
    default_voice: str | None = None
    detail: str | None = None
    voices: list[VoiceInfo] = field(default_factory=list)


def _voice_items(payload: Any) -> list[Any]:
    """Pull the voice list out of either `{"data": [...]}` or a bare list."""
    if isinstance(payload, dict):
        for key in ("voices", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []
    if isinstance(payload, list):
        return payload
    return []


def _pcm16(wav: Any) -> bytes:
    import numpy as np

    audio = np.clip(np.asarray(wav, dtype="float32"), -1.0, 1.0)
    return (audio * 32767.0).astype("<i2").tobytes()


def _wav_bytes(wav: Any, sample_rate: int) -> bytes:
    import soundfile as sf

    buffer = io.BytesIO()
    sf.write(buffer, wav, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def _slug(text: str) -> str:
    text = re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ_-]+", "-", text.strip()).strip("-").lower()
    return text or "voice"


class VoiceBackend(ABC):
    """Common interface for the local and hosted KittenTTS engines."""

    name: str = "base"

    @property
    @abstractmethod
    def ready(self) -> bool: ...

    @property
    @abstractmethod
    def model(self) -> str: ...

    @property
    def sample_rate(self) -> int:
        return cfg.kitten.sample_rate

    @abstractmethod
    async def status(self) -> VoiceStatus: ...

    @abstractmethod
    async def list_voices(self) -> list[VoiceInfo]: ...

    @abstractmethod
    async def transcribe(
        self, audio: bytes, filename: str, language: str | None = None
    ) -> str: ...

    @abstractmethod
    async def synthesize(
        self, text: str, voice: str | None = None, reference: str | None = None
    ) -> bytes:
        """Return a complete audio file (WAV for local, MP3 for hosted)."""

    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        reference: str | None = None,
        response_format: str = "pcm",
    ) -> AsyncIterator[bytes]:
        """Yield audio chunks as they are produced (PCM16 for local)."""

    @abstractmethod
    async def clone_voice(self, name: str, audio: bytes, filename: str) -> VoiceInfo: ...

    async def close(self) -> None:
        return None


# --------------------------------------------------------------------------- #
# Local engine
# --------------------------------------------------------------------------- #
class LocalKittenBackend(VoiceBackend):
    name = "local"

    def __init__(self, settings: KittenSettings) -> None:
        self._settings = settings
        self._model: Any = None
        self._model_lock = asyncio.Lock()
        self._stt: Any = None
        self._stt_lock = asyncio.Lock()
        self._catalog: dict[str, dict[str, Any]] | None = None

    # -- infrastructure ---------------------------------------------------- #
    @property
    def ready(self) -> bool:
        try:
            import kittenml  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    @property
    def model(self) -> str:
        return self._settings.local_repo

    def _resolve_device(self) -> str:
        import torch

        requested = self._settings.device
        if requested == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return requested

    def _load_model(self) -> Any:
        from kittenml import KittenTTS

        device = self._resolve_device()
        try:
            return KittenTTS(self._settings.local_repo, device=device)
        except Exception:  # noqa: BLE001 - MPS can lack ops; fall back to CPU
            if device != "cpu":
                return KittenTTS(self._settings.local_repo, device="cpu")
            raise

    async def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        async with self._model_lock:
            if self._model is None:
                try:
                    self._model = await asyncio.to_thread(self._load_model)
                except Exception as exc:  # noqa: BLE001
                    raise VoiceError(
                        f"Не удалось загрузить локальную модель {self._settings.local_repo}: {exc}"
                    ) from exc
        return self._model

    def _voice_path(self) -> pathlib.Path:
        return pathlib.Path(self._settings.voices_dir)

    def _catalog_path(self) -> pathlib.Path | None:
        repo = pathlib.Path(self._settings.local_repo)
        if repo.is_dir():
            candidate = repo / "voices" / "voices.json"
            return candidate if candidate.is_file() else None
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(repo_id=self._settings.local_repo, filename="voices/voices.json")
            return pathlib.Path(path)
        except Exception:  # noqa: BLE001
            return None

    def _load_catalog(self) -> dict[str, dict[str, Any]]:
        if self._catalog is not None:
            return self._catalog
        path = self._catalog_path()
        catalog: dict[str, dict[str, Any]] = {}
        if path is not None:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    catalog = {str(k): v for k, v in raw.items()}
            except Exception:  # noqa: BLE001
                catalog = {}
        self._catalog = catalog
        return catalog

    def _cloned_index(self) -> dict[str, str]:
        index = self._voice_path() / "index.json"
        if not index.is_file():
            return {}
        try:
            raw = json.loads(index.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def _save_cloned_index(self, data: dict[str, str]) -> None:
        directory = self._voice_path()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "index.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # -- interface --------------------------------------------------------- #
    async def status(self) -> VoiceStatus:
        catalog = await asyncio.to_thread(self._load_catalog)
        voices = self._builtin_info(catalog) + self._cloned_info()
        return VoiceStatus(
            backend=self.name,
            ready=self.ready,
            model=self._settings.local_repo,
            sample_rate=self._settings.sample_rate,
            default_voice=self._settings.voice,
            detail=None if self.ready else "Пакет kittenml не установлен",
            voices=voices,
        )

    def _builtin_info(self, catalog: dict[str, dict[str, Any]]) -> list[VoiceInfo]:
        return [
            VoiceInfo(name=name, title=name, kind="builtin")
            for name in sorted(catalog)
        ]

    def _cloned_info(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(name=name, title=name, kind="cloned")
            for name in sorted(self._cloned_index())
        ]

    async def list_voices(self) -> list[VoiceInfo]:
        catalog = await asyncio.to_thread(self._load_catalog)
        return self._builtin_info(catalog) + self._cloned_info()

    def _reference_for(self, voice: str | None) -> str | None:
        if voice is None:
            return self._settings.reference
        cloned = self._cloned_index().get(voice)
        if cloned:
            return cloned
        return None

    def _speaker_kwargs(self, voice: str | None, reference: str | None) -> dict[str, Any]:
        if reference:
            return {"reference": reference}
        chosen = voice or self._settings.voice
        reference = self._reference_for(chosen)
        if reference:
            return {"reference": reference}
        if chosen:
            return {"voice": chosen}
        return {}

    async def transcribe(
        self, audio: bytes, filename: str, language: str | None = None
    ) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio, filename, language)

    def _load_stt(self) -> Any:
        # Whisper runs on CPU on purpose: the transformers ASR pipeline hangs or
        # produces garbage on the Apple MPS backend, and CPU is fast enough for
        # short utterances.
        from transformers import pipeline

        try:
            return pipeline(
                "automatic-speech-recognition",
                model=self._settings.stt_model,
                chunk_length_s=30,
                device=-1,
            )
        except Exception as exc:  # noqa: BLE001
            raise VoiceError(f"Не удалось загрузить модель распознавания: {exc}") from exc

    def _transcribe_sync(self, audio: bytes, filename: str, language: str | None) -> str:
        import librosa

        if self._stt is None:
            self._stt = self._load_stt()
        suffix = pathlib.Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(audio)
            tmp.flush()
            samples, _ = librosa.load(tmp.name, sr=16000, mono=True)
        lang = language or self._settings.stt_language or None
        generate_kwargs: dict[str, Any] = {"task": "transcribe"}
        if lang and lang != "auto":
            generate_kwargs["language"] = lang
        result = self._stt(samples, generate_kwargs=generate_kwargs)
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        if isinstance(result, list) and result:
            return str(result[0].get("text", "")).strip()
        return ""

    async def synthesize(
        self, text: str, voice: str | None = None, reference: str | None = None
    ) -> bytes:
        model = await self._ensure_model()
        kwargs = self._speaker_kwargs(voice, reference)
        try:
            wav = await asyncio.to_thread(model.generate, text, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise VoiceError(f"Синтез не удался: {exc}") from exc
        return _wav_bytes(wav, model.sample_rate)

    def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        reference: str | None = None,
        response_format: str = "pcm",
    ) -> AsyncIterator[bytes]:
        return self._stream_local(text, voice, reference, response_format)

    async def _stream_local(
        self, text: str, voice: str | None, reference: str | None, response_format: str
    ) -> AsyncIterator[bytes]:
        model = await self._ensure_model()
        kwargs = self._speaker_kwargs(voice, reference)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        done = object()

        def produce() -> None:
            try:
                for chunk in model.generate_stream(text, **kwargs):
                    if response_format == "pcm":
                        payload = _pcm16(chunk)
                    else:
                        payload = _wav_bytes(chunk, model.sample_rate)
                    loop.call_soon_threadsafe(queue.put_nowait, payload)
            except BaseException as exc:  # noqa: BLE001 - re-raised in consumer
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, done)

        future = loop.run_in_executor(None, produce)
        try:
            while True:
                item = await queue.get()
                if item is done:
                    break
                if isinstance(item, BaseException):
                    raise VoiceError(f"Синтез не удался: {item}") from item
                yield item
        finally:
            await future

    async def clone_voice(self, name: str, audio: bytes, filename: str) -> VoiceInfo:
        directory = self._voice_path()
        directory.mkdir(parents=True, exist_ok=True)
        slug = _slug(name)
        target = directory / f"{slug}.wav"
        target.write_bytes(audio)
        index = self._cloned_index()
        index[name] = str(target)
        self._save_cloned_index(index)
        return VoiceInfo(name=name, title=name, kind="cloned")


# --------------------------------------------------------------------------- #
# Hosted engine
# --------------------------------------------------------------------------- #
class HostedKittenBackend(VoiceBackend):
    name = "hosted"

    def __init__(self, settings: KittenSettings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    @property
    def ready(self) -> bool:
        return self._settings.ready

    @property
    def model(self) -> str:
        return self._settings.model

    def _headers(self) -> dict[str, str]:
        key = self._settings.api_key.get_secret_value() if self._settings.api_key else ""
        return {"Authorization": f"Bearer {key}"}

    def _get_client(self) -> httpx.AsyncClient:
        if not self.ready:
            raise VoiceError("KittenML API key is not configured (KITTEN__API_KEY)")
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                headers=self._headers(),
                timeout=self._settings.request_timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        client = self._get_client()
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise VoiceError(f"KittenML API request failed: {exc}") from exc
        if response.status_code >= 400:
            raise VoiceError(
                f"KittenML API {response.status_code}: {response.text[:300]}"
            )
        return response

    async def status(self) -> VoiceStatus:
        voices: list[VoiceInfo] = []
        detail: str | None = None
        if self.ready:
            try:
                voices = await self.list_voices()
            except VoiceError as exc:
                detail = str(exc)
        else:
            detail = "Не задан KITTEN__API_KEY"
        return VoiceStatus(
            backend=self.name,
            ready=self.ready,
            model=self._settings.model,
            sample_rate=self._settings.sample_rate,
            default_voice=self._settings.voice,
            detail=detail,
            voices=voices,
        )

    async def list_voices(self) -> list[VoiceInfo]:
        result: list[VoiceInfo] = []
        seen: set[str] = set()
        after: str | None = None
        # Saved (custom) voices are paginated via `after`; built-in and shared
        # voices are re-sent on every page, so dedupe by id.
        for _ in range(20):
            params: dict[str, str] = {"model": self._settings.model}
            if after:
                params["after"] = after
            response = await self._request("GET", "/voices", params=params)
            payload = response.json()
            items = _voice_items(payload)
            for item in items:
                if not isinstance(item, dict):
                    continue
                voice_id = str(
                    item.get("id") or item.get("voice_id") or item.get("name") or ""
                )
                if not voice_id or voice_id in seen:
                    continue
                seen.add(voice_id)
                title = str(item.get("title") or item.get("name") or voice_id)
                language = item.get("language")
                # `type` is authoritative: only owner-saved voices are "cloned".
                # Public/shared voices reuse the `voice_` id prefix, so the id
                # alone cannot distinguish them from saved ones.
                voice_type = str(item.get("type") or "")
                kind: Literal["builtin", "cloned"] = (
                    "cloned" if voice_type == "custom" else "builtin"
                )
                result.append(
                    VoiceInfo(
                        name=voice_id,
                        title=title,
                        kind=kind,
                        language=str(language) if language else None,
                    )
                )
            has_more = bool(payload.get("has_more")) if isinstance(payload, dict) else False
            last_custom = payload.get("last_custom_id") if isinstance(payload, dict) else None
            if not has_more or not last_custom or last_custom == after:
                break
            after = str(last_custom)
        return result

    async def transcribe(
        self, audio: bytes, filename: str, language: str | None = None
    ) -> str:
        files = {"file": (filename or "audio.wav", audio)}
        data = {"model": "kitten-asr-pro-enhanced", "response_format": "json"}
        if language and language != "auto":
            data["language"] = language
        response = await self._request("POST", "/audio/transcriptions", files=files, data=data)
        payload = response.json()
        if isinstance(payload, dict):
            return str(payload.get("text") or payload.get("transcript") or "").strip()
        return ""

    def _voice_field(self, voice: str | None) -> Any:
        """Built-in voices use a bare id; saved clones must use ``{"id": ...}``."""
        chosen = voice or self._settings.voice
        if not chosen:
            return None
        if chosen.startswith("voice_"):
            return {"id": chosen}
        return chosen

    async def synthesize(
        self, text: str, voice: str | None = None, reference: str | None = None
    ) -> bytes:
        body: dict[str, Any] = {
            "model": self._settings.model,
            "input": text,
            "response_format": "mp3",
        }
        chosen = self._voice_field(voice)
        if chosen is not None:
            body["voice"] = chosen
        response = await self._request("POST", "/audio/speech", json=body)
        return response.content

    async def _stream_hosted(
        self,
        text: str,
        voice: str | None,
        response_format: str,
    ) -> AsyncIterator[bytes]:
        body: dict[str, Any] = {
            "model": self._settings.model,
            "input": text,
            "response_format": response_format,
            "stream_format": "audio",
        }
        chosen = self._voice_field(voice)
        if chosen is not None:
            body["voice"] = chosen
        client = self._get_client()
        try:
            async with client.stream("POST", "/audio/speech", json=body) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", "replace")
                    raise VoiceError(
                        f"KittenML API {response.status_code}: {detail[:300]}"
                    )
                # HTTP chunks arrive at arbitrary byte boundaries. A 16-bit PCM
                # sample can straddle two chunks; the browser decodes each chunk
                # independently, so any misalignment shifts every later sample and
                # turns the stream into static. Buffer and emit 2-byte-aligned
                # chunks, carrying the odd trailing byte over to the next one.
                buffer = b""
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    buffer += chunk
                    usable = len(buffer) - (len(buffer) % 2)
                    if usable:
                        yield buffer[:usable]
                        buffer = buffer[usable:]
                # Drop a lone trailing byte (half a sample) if present.
        except httpx.HTTPError as exc:
            raise VoiceError(f"KittenML API request failed: {exc}") from exc

    def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        reference: str | None = None,
        response_format: str = "pcm",
    ) -> AsyncIterator[bytes]:
        return self._stream_hosted(text, voice, response_format)

    async def clone_voice(self, name: str, audio: bytes, filename: str) -> VoiceInfo:
        files = {"audio_sample": (filename or "reference.wav", audio, "audio/wav")}
        data = {"name": name}
        response = await self._request("POST", "/audio/voices", files=files, data=data)
        payload = response.json()
        voice_id = ""
        if isinstance(payload, dict):
            voice_id = str(payload.get("id") or payload.get("voice_id") or "")
        return VoiceInfo(name=voice_id or name, title=name, kind="cloned")


@lru_cache(maxsize=1)
def get_voice_backend() -> VoiceBackend:
    settings = cfg.kitten
    if settings.resolved_backend == "hosted":
        return HostedKittenBackend(settings)
    return LocalKittenBackend(settings)


__all__ = [
    "HostedKittenBackend",
    "LocalKittenBackend",
    "VoiceBackend",
    "VoiceError",
    "VoiceInfo",
    "VoiceStatus",
    "get_voice_backend",
]
