"""Phase 4.5B: Download visual assets for scenes from Pexels and Pixabay."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import requests

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SCENES_PATH = Path("scenes/scenes.json")
SCENES_OUTPUT_DIR = Path("assets/scenes")
CACHE_DIR = Path("assets/cache")
ASSETS_DIR = Path("assets")

MIN_IMAGE_WIDTH = 1080
MIN_IMAGE_HEIGHT = 1080
CACHE_TTL_SECONDS = 24 * 60 * 60
PROGRESS_STEPS = 7
REQUEST_TIMEOUT = 30

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/"

STOP_WORDS = frozenset(
    """
    a an the and or but in on at to for of with by from as is are was were be been
    being have has had do does did will would could should may might must can this
    that these those it its they them their we you your our not no nor so if then
    than when while where who which what how why all each every both few more most
    other some such only own same into over under again further here there once
    """.split()
)


class VisualAssetAgentError(Exception):
    """Base error for visual asset generation."""


class ScenesNotFoundError(VisualAssetAgentError):
    """scenes/scenes.json is missing or invalid."""


class APIKeyMissingError(VisualAssetAgentError):
    """Required API key is not configured."""


class AssetDownloadError(VisualAssetAgentError):
    """Failed to download or verify an image."""


@dataclass(frozen=True)
class ImageCandidate:
    """A remote image suitable for download."""

    url: str
    width: int
    height: int
    source: str
    photographer: str = ""

    @property
    def pixels(self) -> int:
        return self.width * self.height

    @property
    def is_portrait(self) -> bool:
        return self.height >= self.width

    @property
    def meets_minimum(self) -> bool:
        return self.width >= MIN_IMAGE_WIDTH and self.height >= MIN_IMAGE_HEIGHT

    def score(self) -> float:
        """Rank candidates: resolution, portrait preference, square bonus."""
        score = float(self.pixels)
        if self.is_portrait:
            score *= 1.25
        if self.height >= 1920 and self.width >= 1080:
            score *= 1.1
        return score


@dataclass
class SceneAssetResult:
    scene_number: int
    title: str
    query: str
    status: str
    path: Path | None = None
    source: str | None = None


def keywords_from_description(visual_description: str, title: str = "") -> str:
    """Build a concise stock-photo search query from scene text."""
    text = f"{title} {visual_description}".lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [word for word in text.split() if len(word) > 2 and word not in STOP_WORDS]
    if not words:
        words = visual_description.split()[:6]
    unique: list[str] = []
    seen: set[str] = set()
    for word in words:
        if word not in seen:
            seen.add(word)
            unique.append(word)
        if len(unique) >= 8:
            break
    return " ".join(unique[:8])


class SearchCache:
    """File-based cache for API search results (24-hour TTL)."""

    def __init__(self, cache_dir: Path = CACHE_DIR, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds

    def _path(self, provider: str, query: str, orientation: str = "") -> Path:
        digest = hashlib.sha256(
            f"{provider}:{query.lower()}:{orientation}".encode()
        ).hexdigest()[:16]
        return self.cache_dir / f"{provider}_{digest}.json"

    def get(self, provider: str, query: str, orientation: str = "") -> list[dict[str, Any]] | None:
        path = self._path(provider, query, orientation)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        cached_at = payload.get("cached_at", 0)
        if time.time() - cached_at > self.ttl_seconds:
            logger.debug("Cache expired for %s: %s", provider, query)
            return None
        results = payload.get("results")
        return results if isinstance(results, list) else None

    def set(self, provider: str, query: str, results: list[dict[str, Any]], orientation: str = "") -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(provider, query, orientation)
        payload = {
            "provider": provider,
            "query": query,
            "cached_at": time.time(),
            "results": results,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.debug("Cached %d results for %s: %s", len(results), provider, query)


class PexelsClient:
    """Search and fetch images from Pexels."""

    def __init__(self, api_key: str | None = None, cache: SearchCache | None = None) -> None:
        self.api_key = (api_key or os.environ.get("PEXELS_API_KEY", "")).strip()
        self.cache = cache or SearchCache()
        self.session = requests.Session()
        if self.api_key:
            self.session.headers["Authorization"] = self.api_key

    def _require_key(self) -> None:
        if not self.api_key:
            raise APIKeyMissingError(
                "PEXELS_API_KEY is not set. Add it to your .env file."
            )

    def search(
        self,
        query: str,
        per_page: int = 6,
        orientation: str = "portrait",
    ) -> list[ImageCandidate]:
        """Search Pexels for high-resolution photos (portrait or landscape)."""
        self._require_key()
        cached = self.cache.get("pexels", query, orientation)
        if cached is not None:
            logger.info("Pexels cache hit for query: %s (%s)", query, orientation)
            return [self._candidate_from_cache(item) for item in cached if item]

        params = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
        }
        try:
            response = self.session.get(
                PEXELS_SEARCH_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.error("Pexels search failed for '%s': %s", query, exc)
            return []

        photos = data.get("photos") or []
        candidates: list[ImageCandidate] = []
        cache_payload: list[dict[str, Any]] = []

        for photo in photos:
            if not isinstance(photo, dict):
                continue
            width = int(photo.get("width") or 0)
            height = int(photo.get("height") or 0)
            src = photo.get("src") or {}
            url = (
                src.get("original")
                or src.get("large2x")
                or src.get("large")
                or src.get("portrait")
                or ""
            )
            if not url or width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                continue
            candidate = ImageCandidate(
                url=url,
                width=width,
                height=height,
                source="pexels",
                photographer=str(photo.get("photographer") or ""),
            )
            candidates.append(candidate)
            cache_payload.append(
                {
                    "url": url,
                    "width": width,
                    "height": height,
                    "source": "pexels",
                    "photographer": candidate.photographer,
                }
            )

        self.cache.set("pexels", query, cache_payload, orientation)
        candidates.sort(key=lambda c: c.score(), reverse=True)
        logger.info(
            "Pexels returned %d suitable images for: %s (%s)",
            len(candidates),
            query,
            orientation,
        )
        return candidates

    @staticmethod
    def _candidate_from_cache(item: dict[str, Any]) -> ImageCandidate:
        return ImageCandidate(
            url=str(item["url"]),
            width=int(item["width"]),
            height=int(item["height"]),
            source="pexels",
            photographer=str(item.get("photographer") or ""),
        )


class PixabayClient:
    """Search and fetch images from Pixabay."""

    def __init__(self, api_key: str | None = None, cache: SearchCache | None = None) -> None:
        self.api_key = (api_key or os.environ.get("PIXABAY_API_KEY", "")).strip()
        self.cache = cache or SearchCache()
        self.session = requests.Session()

    def _require_key(self) -> None:
        if not self.api_key:
            raise APIKeyMissingError(
                "PIXABAY_API_KEY is not set. Add it to your .env file."
            )

    def search(
        self,
        query: str,
        per_page: int = 6,
        orientation: str = "vertical",
    ) -> list[ImageCandidate]:
        """Search Pixabay for high-resolution photos (vertical or horizontal)."""
        self._require_key()
        cached = self.cache.get("pixabay", query, orientation)
        if cached is not None:
            logger.info("Pixabay cache hit for query: %s (%s)", query, orientation)
            return [self._candidate_from_cache(item) for item in cached if item]

        params = {
            "key": self.api_key,
            "q": query,
            "image_type": "photo",
            "orientation": orientation,
            "per_page": per_page,
            "min_width": MIN_IMAGE_WIDTH,
            "min_height": MIN_IMAGE_HEIGHT,
            "safesearch": "true",
        }
        try:
            response = self.session.get(
                PIXABAY_SEARCH_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.error("Pixabay search failed for '%s': %s", query, exc)
            return []

        hits = data.get("hits") or []
        candidates: list[ImageCandidate] = []
        cache_payload: list[dict[str, Any]] = []

        for hit in hits:
            if not isinstance(hit, dict):
                continue
            width = int(hit.get("imageWidth") or 0)
            height = int(hit.get("imageHeight") or 0)
            url = (
                hit.get("largeImageURL")
                or hit.get("fullHDURL")
                or hit.get("webformatURL")
                or ""
            )
            if not url or width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                continue
            candidate = ImageCandidate(
                url=url,
                width=width,
                height=height,
                source="pixabay",
                photographer=str(hit.get("user") or ""),
            )
            candidates.append(candidate)
            cache_payload.append(
                {
                    "url": url,
                    "width": width,
                    "height": height,
                    "source": "pixabay",
                    "photographer": candidate.photographer,
                }
            )

        self.cache.set("pixabay", query, cache_payload, orientation)
        candidates.sort(key=lambda c: c.score(), reverse=True)
        logger.info(
            "Pixabay returned %d suitable images for: %s (%s)",
            len(candidates),
            query,
            orientation,
        )
        return candidates

    @staticmethod
    def _candidate_from_cache(item: dict[str, Any]) -> ImageCandidate:
        return ImageCandidate(
            url=str(item["url"]),
            width=int(item["width"]),
            height=int(item["height"]),
            source="pixabay",
            photographer=str(item.get("photographer") or ""),
        )


def landscape_image_score(candidate: ImageCandidate) -> float:
    """Rank stock photos for 1280×720 thumbnails."""
    score = float(candidate.pixels)
    if candidate.width >= candidate.height:
        score *= 1.3
    if candidate.width >= 1280 and candidate.height >= 720:
        score *= 1.15
    return score


class VisualAssetAgent:
    """Download scene images from Pexels (primary) and Pixabay (fallback)."""

    def __init__(
        self,
        scenes_path: Path | str = SCENES_PATH,
        output_dir: Path | str = SCENES_OUTPUT_DIR,
        cache_dir: Path | str = CACHE_DIR,
        pexels_client: PexelsClient | None = None,
        pixabay_client: PixabayClient | None = None,
    ) -> None:
        self.scenes_path = Path(scenes_path)
        self.output_dir = Path(output_dir)
        self.cache = SearchCache(Path(cache_dir))
        self.pexels = pexels_client or PexelsClient(cache=self.cache)
        self.pixabay = pixabay_client or PixabayClient(cache=self.cache)
        self._scenes: list[dict[str, Any]] = []
        self._queries: dict[int, str] = {}
        self._candidates: dict[int, ImageCandidate | None] = {}

    def generate(self) -> list[SceneAssetResult]:
        """Download visual assets for all scenes in scenes.json."""
        if not self.pexels.api_key and not self.pixabay.api_key:
            raise APIKeyMissingError(
                "No API keys configured. Set PEXELS_API_KEY and/or PIXABAY_API_KEY in .env"
            )
        self._ensure_dirs()
        self._print_progress(1, "Reading scenes...")
        self._read_scenes()

        self._print_progress(2, "Generating search queries...")
        self._build_queries()

        self._print_progress(3, "Searching Pexels...")
        self._search_pexels()

        self._print_progress(4, "Searching Pixabay...")
        self._search_pixabay_fallback()

        self._print_progress(5, "Downloading assets...")
        results = self._download_assets()

        self._print_progress(6, "Verifying images...")
        self._verify_downloads(results)

        self._print_progress(7, "Completed")
        self._print_summary(results)
        return results

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _ensure_dirs(self) -> None:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache.cache_dir.mkdir(parents=True, exist_ok=True)

    def _read_scenes(self) -> None:
        if not self.scenes_path.is_file():
            raise ScenesNotFoundError(
                f"Scenes file not found: {self.scenes_path}. Run Phase 4.5A first."
            )
        try:
            data = json.loads(self.scenes_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenesNotFoundError(f"Cannot read scenes file: {exc}") from exc

        if isinstance(data, dict) and "scenes" in data:
            data = data["scenes"]
        if not isinstance(data, list) or not data:
            raise ScenesNotFoundError("scenes.json must contain a non-empty scene list.")

        self._scenes = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                scene_number = int(item["scene_number"])
            except (KeyError, TypeError, ValueError):
                continue
            title = str(item.get("title") or f"Scene {scene_number}").strip()
            visual_description = str(item.get("visual_description") or "").strip()
            if not visual_description:
                continue
            self._scenes.append(
                {
                    "scene_number": scene_number,
                    "title": title,
                    "visual_description": visual_description,
                }
            )

        self._scenes.sort(key=lambda s: s["scene_number"])
        if not self._scenes:
            raise ScenesNotFoundError("No valid scenes found in scenes.json.")
        logger.info("Loaded %d scenes from %s", len(self._scenes), self.scenes_path)

    def _build_queries(self) -> None:
        for scene in self._scenes:
            number = scene["scene_number"]
            query = keywords_from_description(
                scene["visual_description"],
                scene["title"],
            )
            self._queries[number] = query
            logger.info("Scene %d query: %s", number, query)
            print(f"  Scene {number}: {query}", flush=True)

    def _search_pexels(self) -> None:
        pexels_enabled = bool(self.pexels.api_key)
        if not pexels_enabled:
            logger.warning("PEXELS_API_KEY not set; skipping Pexels search.")

        for scene in self._scenes:
            number = scene["scene_number"]
            if not pexels_enabled:
                self._candidates[number] = None
                continue
            query = self._queries[number]
            candidates = self.pexels.search(query)
            self._candidates[number] = candidates[0] if candidates else None
            if self._candidates[number]:
                logger.info("Scene %d: Pexels match found", number)

    def _search_pixabay_fallback(self) -> None:
        pixabay_enabled = bool(self.pixabay.api_key)
        if not pixabay_enabled:
            logger.warning("PIXABAY_API_KEY not set; skipping Pixabay search.")

        for scene in self._scenes:
            number = scene["scene_number"]
            if self._candidates.get(number):
                continue
            if not pixabay_enabled:
                continue
            query = self._queries[number]
            candidates = self.pixabay.search(query)
            self._candidates[number] = candidates[0] if candidates else None
            if self._candidates[number]:
                logger.info("Scene %d: Pixabay match found", number)

    def _download_assets(self) -> list[SceneAssetResult]:
        results: list[SceneAssetResult] = []
        session = requests.Session()
        session.headers["User-Agent"] = "YT-Agent/1.0 (visual-asset-agent)"

        for scene in self._scenes:
            number = scene["scene_number"]
            title = scene["title"]
            query = self._queries[number]
            candidate = self._candidates.get(number)

            if candidate is None:
                logger.warning("No visual asset found for Scene %d", number)
                results.append(
                    SceneAssetResult(
                        scene_number=number,
                        title=title,
                        query=query,
                        status="not found",
                    )
                )
                continue

            output_path = self.output_dir / f"scene_{number}.jpg"
            try:
                self._download_image(session, candidate.url, output_path)
                results.append(
                    SceneAssetResult(
                        scene_number=number,
                        title=title,
                        query=query,
                        status="downloaded",
                        path=output_path,
                        source=candidate.source,
                    )
                )
                logger.info(
                    "Scene %d downloaded from %s -> %s",
                    number,
                    candidate.source,
                    output_path,
                )
            except AssetDownloadError as exc:
                logger.error("Scene %d download failed: %s", number, exc)
                results.append(
                    SceneAssetResult(
                        scene_number=number,
                        title=title,
                        query=query,
                        status="download failed",
                    )
                )

        return results

    def _download_image(
        self,
        session: requests.Session,
        url: str,
        output_path: Path,
    ) -> None:
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            content = response.content
        except requests.RequestException as exc:
            raise AssetDownloadError(f"Download request failed: {exc}") from exc

        if len(content) < 50_000:
            raise AssetDownloadError(
                f"Downloaded file too small ({len(content)} bytes); likely not a valid image."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

    def _verify_downloads(self, results: list[SceneAssetResult]) -> None:
        try:
            from PIL import Image
        except ImportError as exc:
            raise VisualAssetAgentError(
                "Pillow is required for image verification. Run: pip install Pillow"
            ) from exc

        for result in results:
            if result.status != "downloaded" or result.path is None:
                continue
            try:
                with Image.open(result.path) as img:
                    width, height = img.size
                    image_format = img.format
                    if image_format and image_format.upper() not in ("JPEG", "JPG"):
                        rgb = img.convert("RGB")
                        rgb.save(result.path, "JPEG", quality=92)
            except OSError as exc:
                result.status = "invalid"
                if result.path.exists():
                    result.path.unlink()
                logger.error(
                    "Scene %d image verification failed: %s",
                    result.scene_number,
                    exc,
                )
                continue

            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                result.status = "rejected (too small)"
                result.path.unlink(missing_ok=True)
                logger.warning(
                    "Scene %d rejected: %dx%d below minimum %dx%d",
                    result.scene_number,
                    width,
                    height,
                    MIN_IMAGE_WIDTH,
                    MIN_IMAGE_HEIGHT,
                )
                continue

            logger.info(
                "Scene %d verified: %dx%d",
                result.scene_number,
                width,
                height,
            )

    def _print_summary(self, results: list[SceneAssetResult]) -> None:
        print("\nVisual asset summary:", flush=True)
        for result in sorted(results, key=lambda r: r.scene_number):
            if result.status == "downloaded":
                source = result.source or "unknown"
                print(
                    f"  Scene {result.scene_number} -> downloaded ({source})",
                    flush=True,
                )
            else:
                print(
                    f"  Scene {result.scene_number} -> {result.status}",
                    flush=True,
                )
