from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI


class EmbeddingService:
    """Embedding service backed by a compatible OpenAI embeddings API."""

    BATCH_SIZE = 10
    MAX_RETRY = 3
    RETRY_DELAY_MS = 1000

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        project_env = project_root / ".env"
        load_dotenv(project_env, override=False)

        self.base_url = (
            base_url
            or os.getenv("embedding_url")
        )
        self.api_key = (
            api_key
            or os.getenv("embedding_api")
        )
        self.model = (
            model
            or os.getenv("embedding_model")
            or "text-embedding-v4"
        )
        self.dimensions = dimensions
        if self.dimensions is None:
            dimensions_value = os.getenv("dimention")
            self.dimensions = int(dimensions_value) if dimensions_value else 1024

        if not self.base_url or not self.api_key:
            raise RuntimeError("Please set BASE_URL and API_KEY in .env or environment variables.")

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            return []
        embeddings = self.embed_batch([text])
        return embeddings[0] if embeddings else []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start : start + self.BATCH_SIZE]
            batch_embeddings = self._call_embedding_api(batch)
            all_embeddings.extend(batch_embeddings)
        return all_embeddings

    def get_dimensions(self) -> int:
        return self.dimensions

    def _call_embedding_api(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_RETRY + 1):
            try:
                request: dict[str, object] = {
                    "model": self.model,
                    "input": texts,
                }
                if self.dimensions is not None:
                    request["dimensions"] = self.dimensions

                response = self.client.embeddings.create(**request)
                sorted_data = sorted(response.data, key=lambda item: item.index)
                return [item.embedding for item in sorted_data]
            except Exception as error:
                last_error = error
                print(
                    f"Embedding API failed, attempt {attempt}/{self.MAX_RETRY}: {error}"
                )
                if attempt < self.MAX_RETRY:
                    delay_ms = min(self.RETRY_DELAY_MS * (2 ** (attempt - 1)), 10000)
                    time.sleep(delay_ms / 1000)

        raise RuntimeError(
            f"Embedding failed after {self.MAX_RETRY} retries: {last_error}"
        ) from last_error
