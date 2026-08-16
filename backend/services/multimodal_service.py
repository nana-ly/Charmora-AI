from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

import httpx
from openai import OpenAI
from PIL import Image, UnidentifiedImageError
from mutagen import File as MutagenFile
from sqlalchemy.orm import Session

from core.config import MultimodalConfig
from core.errors import AppError
from db.repositories.products import ProductRepository
from schemas.catalog import ProductView
from services.catalog_service import CatalogService

IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
AUDIO_TYPES = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
}


class ImageEmbeddingProvider(Protocol):
    def embed(self, content: bytes, mime_type: str) -> list[float]: ...


class VisionUnderstandingProvider(Protocol):
    def understand(self, content: bytes, mime_type: str, prompt: str) -> str: ...


class SpeechRecognitionProvider(Protocol):
    def transcribe(self, content: bytes, filename: str) -> str: ...


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str) -> bytes: ...


class AssetStore:
    def __init__(self, root: str | Path) -> None:
        path = Path(root)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        self.root = path.resolve()

    def save(self, content: bytes, suffix: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        asset_id = f"{uuid4().hex}{suffix}"
        destination = (self.root / asset_id).resolve()
        if self.root not in destination.parents:
            raise AppError("invalid_upload_path", "上传文件路径无效。")
        destination.write_bytes(content)
        return asset_id


class ExternalImageEmbeddingProvider:
    def __init__(self, url: str, api_key: str) -> None:
        self.url = url
        self.api_key = api_key

    def embed(self, content: bytes, mime_type: str) -> list[float]:
        response = httpx.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json={
                "image": base64.b64encode(content).decode("ascii"),
                "mime_type": mime_type,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload.get("embedding")
        if embedding is None and payload.get("data"):
            embedding = payload["data"][0].get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise RuntimeError("image embedding provider returned no vector")
        return [float(value) for value in embedding]


class OpenAIVisionProvider:
    def __init__(self, config: MultimodalConfig) -> None:
        self.client = OpenAI(api_key=config.vision_api_key, base_url=config.vision_base_url)
        self.model = config.vision_model

    def understand(self, content: bytes, mime_type: str, prompt: str) -> str:
        image_url = f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=500,
        )
        return (response.choices[0].message.content or "").strip()


class OpenAIAsrProvider:
    def __init__(self, config: MultimodalConfig) -> None:
        self.client = OpenAI(api_key=config.asr_api_key, base_url=config.asr_base_url)
        self.model = config.asr_model

    def transcribe(self, content: bytes, filename: str) -> str:
        stream = io.BytesIO(content)
        stream.name = filename
        response = self.client.audio.transcriptions.create(model=self.model, file=stream)
        return str(response.text).strip()


class OpenAITtsProvider:
    def __init__(self, config: MultimodalConfig) -> None:
        self.client = OpenAI(api_key=config.tts_api_key, base_url=config.tts_base_url)
        self.model = config.tts_model
        self.voice = config.tts_voice

    def synthesize(self, text: str) -> bytes:
        response = self.client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="mp3",
        )
        return response.read()


class MultimodalService:
    def __init__(self, config: MultimodalConfig, session: Session) -> None:
        self.config = config
        self.session = session
        self.assets = AssetStore(config.upload_root)

    def validate_image(self, content: bytes, mime_type: str) -> str:
        suffix = IMAGE_TYPES.get(mime_type)
        if suffix is None:
            raise AppError("unsupported_image_type", "仅支持 JPEG、PNG 和 WebP 图片。", status_code=415)
        if not content or len(content) > self.config.max_image_bytes:
            raise AppError("invalid_image_size", "图片为空或超过大小限制。", status_code=413)
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 25_000_000:
                    raise AppError("image_dimensions_too_large", "图片像素尺寸过大。", status_code=413)
        except UnidentifiedImageError as exc:
            raise AppError("invalid_image", "无法识别上传的图片。", status_code=400) from exc
        return suffix

    def understand_image(self, content: bytes, mime_type: str, prompt: str) -> tuple[str, str]:
        suffix = self.validate_image(content, mime_type)
        if not self.config.vision_enabled or not self.config.vision_api_key:
            raise _capability("vision")
        asset_id = self.assets.save(content, suffix)
        description = OpenAIVisionProvider(self.config).understand(content, mime_type, prompt)
        if not description:
            raise AppError("empty_vision_result", "图片理解服务没有返回有效结果。", status_code=502)
        return asset_id, description

    def search_image(self, content: bytes, mime_type: str, top_k: int) -> tuple[str, list[ProductView]]:
        suffix = self.validate_image(content, mime_type)
        if not self.config.image_embedding_url:
            raise _capability("image_similarity")
        embedding = ExternalImageEmbeddingProvider(
            self.config.image_embedding_url,
            self.config.image_embedding_api_key,
        ).embed(content, mime_type)
        from retrieval.vector import VectorRetriever

        rows = VectorRetriever().store.query_by_embedding(embedding, top_k=max(top_k * 5, 20))
        ids: list[UUID] = []
        for row in rows:
            try:
                ids.append(UUID(str(row.get("product_id"))))
            except (TypeError, ValueError):
                continue
        products = ProductRepository(self.session).eligible_by_ids(ids)[:top_k]
        asset_id = self.assets.save(content, suffix)
        return asset_id, [CatalogService.to_view(product) for product in products]

    def validate_audio(self, content: bytes, mime_type: str) -> str:
        suffix = AUDIO_TYPES.get(mime_type)
        if suffix is None:
            raise AppError("unsupported_audio_type", "不支持该音频格式。", status_code=415)
        if not content or len(content) > self.config.max_audio_bytes:
            raise AppError("invalid_audio_size", "音频为空或超过大小限制。", status_code=413)
        try:
            audio = MutagenFile(io.BytesIO(content))
            duration = float(audio.info.length) if audio is not None and audio.info else 0.0
        except Exception as exc:
            raise AppError("invalid_audio", "无法读取音频内容。", status_code=400) from exc
        if duration <= 0:
            raise AppError("invalid_audio", "无法读取音频时长。", status_code=400)
        if duration > self.config.max_audio_seconds:
            raise AppError(
                "audio_duration_too_long",
                "音频时长超过限制。",
                status_code=413,
                details={"max_seconds": self.config.max_audio_seconds},
            )
        return suffix

    def transcribe(self, content: bytes, mime_type: str) -> str:
        suffix = self.validate_audio(content, mime_type)
        if not self.config.asr_enabled or not self.config.asr_api_key:
            raise _capability("asr")
        return OpenAIAsrProvider(self.config).transcribe(content, f"audio{suffix}")

    def synthesize(self, text: str) -> bytes:
        if not self.config.tts_enabled or not self.config.tts_api_key:
            raise _capability("tts")
        return OpenAITtsProvider(self.config).synthesize(text)


def _capability(name: str) -> AppError:
    return AppError(
        "capability_unavailable",
        "该多模态能力尚未配置。",
        status_code=503,
        details={"capability": name},
    )
