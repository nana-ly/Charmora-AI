from __future__ import annotations

import json
from typing import Protocol

import httpx

from services.import_parsers import ProductImportParseResult, parse_product_file_result


class ProductSourceAdapter(Protocol):
    """Adapter boundary for authorized product sources."""

    def fetch(self) -> ProductImportParseResult: ...


class AuthorizedApiSourceAdapter:
    """Fetch an authorized JSON catalog without exposing credentials to clients."""

    def __init__(
        self,
        endpoint: str,
        token: str,
        *,
        client: httpx.Client | None = None,
        default_inventory: int = 0,
    ) -> None:
        if not endpoint.lower().startswith("https://"):
            raise ValueError("authorized product API endpoint must use HTTPS")
        self.endpoint = endpoint
        self.token = token
        self.client = client or httpx.Client(timeout=30)
        self.default_inventory = default_inventory

    def fetch(self) -> ProductImportParseResult:
        response = self.client.get(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        response.raise_for_status()
        return parse_product_file_result(
            json.dumps(response.json(), ensure_ascii=False).encode("utf-8"),
            "authorized-api.json",
            default_inventory=self.default_inventory,
        )
