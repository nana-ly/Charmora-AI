from __future__ import annotations

import io
import wave

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.multimodal import service as multimodal_dependency
from core.config import MultimodalConfig
from core.errors import AppError
from main import app
from services.multimodal_service import MultimodalService


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), (90, 120, 115)).save(output, format="PNG")
    return output.getvalue()


def _wav_bytes(seconds: int = 1) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 16_000 * seconds)
    return output.getvalue()


def test_image_validation_rejects_mime_spoofing(tmp_path):
    service = MultimodalService(MultimodalConfig(upload_root=str(tmp_path)), None)

    with pytest.raises(AppError) as caught:
        service.validate_image(b"not an image", "image/png")

    assert caught.value.code == "invalid_image"


def test_unconfigured_vision_returns_stable_capability_error(tmp_path):
    service = MultimodalService(MultimodalConfig(upload_root=str(tmp_path)), None)

    with pytest.raises(AppError) as caught:
        service.understand_image(_png_bytes(), "image/png", "describe")

    assert caught.value.code == "capability_unavailable"
    assert caught.value.status_code == 503
    assert caught.value.details == {"capability": "vision"}
    assert list(tmp_path.iterdir()) == []


def test_audio_validation_checks_real_duration(tmp_path):
    config = MultimodalConfig(upload_root=str(tmp_path), max_audio_seconds=1)
    service = MultimodalService(config, None)

    with pytest.raises(AppError) as caught:
        service.validate_audio(_wav_bytes(seconds=2), "audio/wav")

    assert caught.value.code == "audio_duration_too_long"
    assert caught.value.details == {"max_seconds": 1}


def test_multimodal_api_uses_standard_error_contract(tmp_path):
    configured = MultimodalService(MultimodalConfig(upload_root=str(tmp_path)), None)
    app.dependency_overrides[multimodal_dependency] = lambda: configured
    try:
        response = TestClient(app).post(
            "/multimodal/images/understand",
            files={"file": ("item.png", _png_bytes(), "image/png")},
        )
    finally:
        app.dependency_overrides.pop(multimodal_dependency, None)

    assert response.status_code == 503
    assert response.json()["code"] == "capability_unavailable"
    assert response.json()["message"]
    assert response.json()["request_id"]
    assert response.json()["details"] == {"capability": "vision"}


def test_validation_errors_have_stable_code_and_traceable_request_id():
    response = TestClient(app).post(
        "/multimodal/tts",
        headers={"X-Request-ID": "contract-request-id"},
        json={"text": ""},
    )

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "contract-request-id"
    assert response.json()["code"] == "validation_error"
    assert response.json()["request_id"] == "contract-request-id"
    assert response.json()["details"]["errors"]
