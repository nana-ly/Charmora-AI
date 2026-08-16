"""Download one freely licensed Wikimedia Commons reference image per category."""

from __future__ import annotations

import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "ecommerce_agent_dataset" / "synthetic_lifestyle_v1" / "images"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "ShopGuide-RAG demo catalog/1.0"
CATEGORIES = [
    (1, "Hair clips"),
    (2, "Plush toys"),
    (3, "Handbags"),
    (4, "Makeup brushes"),
    (5, "Stationery"),
    (6, "Storage containers"),
    (7, "Gift boxes"),
]
ALLOWED_LICENSE_MARKERS = ("CC BY", "CC0", "Public domain")


def _json(url: str) -> dict:
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError("unreachable")


def _download(url: str, target: Path) -> None:
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=60) as response:
                target.write_bytes(response.read())
            return
        except OSError:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def _pick(category: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "generator": "categorymembers",
        "gcmtitle": f"Category:{category}",
        "gcmtype": "file",
        "gcmlimit": 30,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 900,
        "origin": "*",
    }
    payload = _json(f"{API}?{urlencode(params)}")
    pages = payload.get("query", {}).get("pages", {})
    for page in sorted(pages.values(), key=lambda value: value.get("title", "")):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = meta.get("LicenseShortName", {}).get("value", "")
        url = info.get("thumburl") or info.get("url")
        if url and any(marker in license_name for marker in ALLOWED_LICENSE_MARKERS):
            return {
                "title": page.get("title", ""),
                "url": url,
                "page_url": info.get("descriptionurl", ""),
                "license": license_name,
                "artist": meta.get("Artist", {}).get("value", "Unknown"),
            }
    raise RuntimeError(f"no suitable freely licensed image found for {category}")


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    attributions: list[dict] = []
    for index, category in CATEGORIES:
        picked = _pick(category)
        raw = IMAGE_DIR / f"category-{index:02d}.download"
        target = IMAGE_DIR / f"category-{index:02d}.jpg"
        _download(picked["url"], raw)
        with Image.open(raw) as source:
            image = ImageOps.fit(source.convert("RGB"), (900, 900), method=Image.Resampling.LANCZOS)
            image.save(target, "JPEG", quality=86, optimize=True)
        raw.unlink()
        picked["category"] = category
        picked["local_file"] = target.name
        attributions.append(picked)
        print(f"downloaded {category} -> {target.name}")

    lines = ["# Image attribution", "", "Images are local demo references downloaded from Wikimedia Commons.", ""]
    for item in attributions:
        lines.extend(
            [
                f"- `{item['local_file']}` — {item['title']}",
                f"  - Category: {item['category']}",
                f"  - Source: {item['page_url']}",
                f"  - License: {item['license']}",
                f"  - Artist: {item['artist']}",
            ]
        )
    (IMAGE_DIR / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
