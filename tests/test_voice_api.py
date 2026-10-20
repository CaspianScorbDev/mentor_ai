from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import main
from app.core.config import KittenSettings
from app.integrations.base import StreamChunk
from app.integrations.kitten import (
    HostedKittenBackend,
    VoiceBackend,
    VoiceInfo,
    VoiceStatus,
    get_voice_backend,
)
from app.services.llm import ChatTurn, Persona, get_llm_service, strip_voice_tags


class FakeVoiceBackend(VoiceBackend):
    name = "local"

    def __init__(self, ready: bool = True) -> None:
        self._ready = ready

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def model(self) -> str:
        return "fake-model"

    async def status(self) -> VoiceStatus:
        return VoiceStatus(
            backend=self.name,
            ready=self._ready,
            model=self.model,
            sample_rate=24000,
            default_voice="Bruno",
            voices=await self.list_voices(),
        )

    async def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(name="Bruno", title="Bruno"),
            VoiceInfo(name="clone-1", title="My Voice", kind="cloned"),
        ]

    async def transcribe(
        self, audio: bytes, filename: str, language: str | None = None
    ) -> str:
        return "привет мир"

    async def synthesize(
        self, text: str, voice: str | None = None, reference: str | None = None
    ) -> bytes:
        return b"RIFFfakewav"

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        reference: str | None = None,
        fmt: str = "pcm",
    ) -> AsyncIterator[bytes]:
        yield b"\x00\x00" * 8

    async def clone_voice(self, name: str, audio: bytes, filename: str) -> VoiceInfo:
        return VoiceInfo(name=name, title=name, kind="cloned")

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def voice_client() -> AsyncIterator[AsyncClient]:
    backend = FakeVoiceBackend()
    main.app.dependency_overrides[get_voice_backend] = lambda: backend
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as http_client:
        yield http_client
    main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def not_ready_client() -> AsyncIterator[AsyncClient]:
    backend = FakeVoiceBackend(ready=False)
    main.app.dependency_overrides[get_voice_backend] = lambda: backend
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as http_client:
        yield http_client
    main.app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_status(voice_client: AsyncClient) -> None:
    response = await voice_client.get("/api/v1/voice/status")
    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "local"
    assert body["ready"] is True
    assert body["default_voice"] == "Bruno"
    assert len(body["voices"]) == 2
    assert body["voices"][1]["kind"] == "cloned"


@pytest.mark.asyncio
async def test_list_voices(voice_client: AsyncClient) -> None:
    response = await voice_client.get("/api/v1/voice/voices")
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["Bruno", "clone-1"]


@pytest.mark.asyncio
async def test_transcribe(voice_client: AsyncClient) -> None:
    response = await voice_client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("sample.wav", b"audio-bytes", "audio/wav")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "привет мир"


@pytest.mark.asyncio
async def test_transcribe_empty(voice_client: AsyncClient) -> None:
    response = await voice_client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("sample.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_speak(voice_client: AsyncClient) -> None:
    response = await voice_client.post("/api/v1/voice/speak", json={"text": "привет"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content == b"RIFFfakewav"


@pytest.mark.asyncio
async def test_speak_rejects_long_text(voice_client: AsyncClient) -> None:
    response = await voice_client.post(
        "/api/v1/voice/speak", json={"text": "а" * 5000}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_speak_not_ready(not_ready_client: AsyncClient) -> None:
    response = await not_ready_client.post("/api/v1/voice/speak", json={"text": "привет"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_clone(voice_client: AsyncClient) -> None:
    response = await voice_client.post(
        "/api/v1/voice/clone",
        files={"file": ("ref.wav", b"audio-bytes", "audio/wav")},
        data={"name": "Мой голос"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Мой голос"
    assert body["kind"] == "cloned"


def test_tts_websocket_streams_pcm(monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.testclient import TestClient
    from starlette.types import ASGIApp, Receive, Scope, Send

    import app.backend.api.voice as voice_module
    import app.backend.server as server_module

    class NoTrustedHost:
        def __init__(self, app: ASGIApp, **_kwargs: object) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            await self.app(scope, receive, send)

    monkeypatch.setattr(server_module, "TrustedHostMiddleware", NoTrustedHost)
    monkeypatch.setattr(voice_module, "get_voice_backend", lambda: FakeVoiceBackend())

    app = server_module.create_app()
    client = TestClient(app, base_url="http://localhost")
    with client.websocket_connect("/api/v1/voice/tts") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["sample_rate"] == 24000

        ws.send_json({"type": "speak", "text": "привет"})
        audio_chunks: list[str] = []
        while True:
            message = ws.receive_json()
            if message["type"] == "audio":
                audio_chunks.append(message["data"])
            elif message["type"] == "done":
                break
        assert audio_chunks


def test_strip_voice_tags() -> None:
    assert strip_voice_tags("[joyful] Привет! <laugh>") == "Привет!"
    assert strip_voice_tags("Смотри [тут](http://a) сейчас") == "Смотри [тут](http://a) сейчас"
    assert strip_voice_tags("[tender]Как дела?") == "Как дела?"


class _TaggedLLM:
    async def stream(
        self, persona: Persona, turns: list[ChatTurn]
    ) -> AsyncIterator[StreamChunk]:
        for token in ("[joyful] Привет! ", "<laugh> Рад ", "тебя видеть."):
            yield StreamChunk("content", token)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_voice_message_streams_tags_but_stores_clean(client: AsyncClient) -> None:
    main.app.dependency_overrides[get_llm_service] = lambda: _TaggedLLM()

    created = await client.post("/api/v1/chats", json={"title": "voice"})
    chat_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"content": "привет", "voice": True},
    )
    assert response.status_code == 200
    assert "[joyful]" in response.text

    detail = await client.get(f"/api/v1/chats/{chat_id}")
    messages = detail.json()["messages"]
    ai_message = [m for m in messages if m["role"] == "ai"][-1]
    assert "[joyful]" not in ai_message["content"]
    assert "<laugh>" not in ai_message["content"]
    assert ai_message["content"] == "Привет! Рад тебя видеть."


def test_kitten_auto_backend_resolution() -> None:
    with_key = KittenSettings(api_key="sk_kitten_live_test")
    assert with_key.resolved_backend == "hosted"
    assert with_key.ready is True

    without_key = KittenSettings()
    assert without_key.resolved_backend == "local"
    assert without_key.ready is True

    forced_local = KittenSettings(backend="local", api_key="sk_kitten_live_test")
    assert forced_local.resolved_backend == "local"

    forced_hosted_no_key = KittenSettings(backend="hosted")
    assert forced_hosted_no_key.resolved_backend == "hosted"
    assert forced_hosted_no_key.ready is False


def test_hosted_voice_field_wraps_saved_voices() -> None:
    backend = HostedKittenBackend(KittenSettings(api_key="sk_kitten_live_test"))
    assert backend._voice_field("bruno") == "bruno"
    assert backend._voice_field("voice_abc123") == {"id": "voice_abc123"}
    assert backend._voice_field(None) is None


class _FakeStreamResponse:
    status_code = 200

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def aread(self) -> bytes:
        return b""

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class _FakeStreamContext:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def __aenter__(self) -> _FakeStreamResponse:
        return _FakeStreamResponse(self._chunks)

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeHostedClient:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def stream(self, *_args: object, **_kwargs: object) -> _FakeStreamContext:
        return _FakeStreamContext(self._chunks)


@pytest.mark.asyncio
async def test_hosted_stream_emits_byte_aligned_pcm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = HostedKittenBackend(KittenSettings(api_key="sk_kitten_live_test"))
    # 769 bytes -> odd length; split into 3-byte pieces so every chunk is odd.
    payload = bytes(range(256)) * 3 + b"\x01"
    chunks = [payload[i : i + 3] for i in range(0, len(payload), 3)]
    monkeypatch.setattr(backend, "_get_client", lambda: _FakeHostedClient(chunks))

    out = [chunk async for chunk in backend.synthesize_stream("hi", "russian_45")]

    assert out
    assert all(len(chunk) % 2 == 0 for chunk in out)
    assert b"".join(out) == payload[:-1]


def test_ollama_client_disables_thinking() -> None:
    from app.integrations.ollama import OllamaClient

    client = OllamaClient()
    assert client._extra_body == {"reasoning_effort": "none"}


EMOTION_TAGS = [
    "angry",
    "contemplative",
    "excited",
    "joyful",
    "mundane",
    "nervous",
    "sad",
    "stern",
    "surprised",
    "tender",
]
SOUND_TAGS = ["gasp", "giggle", "growl", "gulp", "laugh", "scoff", "sigh", "sob"]


def test_strip_all_documented_voice_tags() -> None:
    text = (
        " ".join(f"[{tag}]" for tag in EMOTION_TAGS)
        + " "
        + " ".join(f"<{tag}>" for tag in SOUND_TAGS)
        + " Привет"
    )
    assert strip_voice_tags(text) == "Привет"


def test_voice_style_prompt_lists_all_tags() -> None:
    from app.services.llm import VOICE_STYLE_PROMPT

    for tag in EMOTION_TAGS:
        assert f"[{tag}]" in VOICE_STYLE_PROMPT
    for tag in SOUND_TAGS:
        assert f"<{tag}>" in VOICE_STYLE_PROMPT


class _FakeJsonResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload


@pytest.mark.asyncio
async def test_hosted_list_voices_paginates_and_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = HostedKittenBackend(KittenSettings(api_key="sk_kitten_live_test"))
    pages: dict[str | None, dict[str, object]] = {
        None: {
            "data": [
                {"id": "bella_10", "name": "Bella", "type": "built_in"},
                {"id": "voice_pub", "name": "Mr Harvard", "type": "public"},
            ],
            "has_more": True,
            "last_custom_id": "voice_c1",
        },
        "voice_c1": {
            "data": [
                {"id": "bella_10", "name": "Bella", "type": "built_in"},
                {"id": "voice_pub", "name": "Mr Harvard", "type": "public"},
                {"id": "voice_c1", "name": "Radmir", "type": "custom"},
            ],
            "has_more": False,
            "last_custom_id": "voice_c1",
        },
    }
    seen_after: list[str | None] = []

    async def fake_request(_method: str, _path: str, **kwargs: object) -> _FakeJsonResponse:
        params = kwargs.get("params")
        after = params.get("after") if isinstance(params, dict) else None
        seen_after.append(after)
        return _FakeJsonResponse(pages[after])

    monkeypatch.setattr(backend, "_request", fake_request)
    voices = await backend.list_voices()

    ids = [v.name for v in voices]
    assert ids.count("bella_10") == 1
    assert ids.count("voice_pub") == 1
    radmir = next(v for v in voices if v.name == "voice_c1")
    assert radmir.kind == "cloned"
    assert radmir.title == "Radmir"
    assert next(v for v in voices if v.name == "voice_pub").kind == "builtin"
    assert seen_after == [None, "voice_c1"]






