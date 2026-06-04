"""Topic-keyed cache for timeline assets, thumbnails, and search reuse."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TOPIC_CACHE_ROOT = Path("assets/cache/topics")
TIMELINE_DIR = Path("assets/timeline")
THUMBNAIL_PATH = Path("thumbnails/output.png")


def topic_cache_key(topic: str) -> str:
    normalized = " ".join(topic.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class TopicAssetCache:
    """Persist and restore assets for repeated runs of the same topic."""

    def __init__(self, topic: str) -> None:
        self.topic = topic.strip()
        self.key = topic_cache_key(self.topic)
        self.root = TOPIC_CACHE_ROOT / self.key
        self.scenes_dir = self.root / "scenes"
        self.manifest_path = self.root / "manifest.json"

    def is_available(self) -> bool:
        return self.manifest_path.is_file() and self.scenes_dir.is_dir()

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return {}
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def try_restore_scene(
        self,
        scene_number: int,
        query: str,
    ) -> tuple[Path | None, str | None, str | None]:
        """
        Copy cached asset into assets/timeline/ if query matches.
        Returns (asset_path, asset_kind, source) or (None, None, None).
        """
        manifest = self._load_manifest()
        scenes = manifest.get("scenes")
        if not isinstance(scenes, dict):
            return None, None, None

        entry = scenes.get(str(scene_number))
        if not isinstance(entry, dict):
            return None, None, None
        if entry.get("query", "").strip().lower() != query.strip().lower():
            return None, None, None

        filename = entry.get("file")
        if not filename:
            return None, None, None
        src = self.scenes_dir / filename
        if not src.is_file() or src.stat().st_size < 10_000:
            return None, None, None

        ext = src.suffix or ".mp4"
        TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
        dest = TIMELINE_DIR / f"scene_{scene_number}{ext}"
        shutil.copy2(src, dest)
        kind = entry.get("asset_kind", "video")
        source = entry.get("source", "cache")
        logger.info(
            "Topic cache hit: scene %d restored from %s",
            scene_number,
            self.key,
        )
        return dest, kind, source

    def save_scene(
        self,
        scene_number: int,
        query: str,
        asset_path: Path,
        asset_kind: str,
        source: str,
    ) -> None:
        if not asset_path.is_file():
            return
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        dest_name = f"scene_{scene_number}{asset_path.suffix}"
        dest = self.scenes_dir / dest_name
        shutil.copy2(asset_path, dest)

        manifest = self._load_manifest()
        scenes = manifest.setdefault("scenes", {})
        if not isinstance(scenes, dict):
            scenes = {}
            manifest["scenes"] = scenes
        scenes[str(scene_number)] = {
            "query": query,
            "file": dest_name,
            "asset_kind": asset_kind,
            "source": source,
        }
        manifest["topic"] = self.topic
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def save_thumbnail(self, thumbnail_path: Path = THUMBNAIL_PATH) -> None:
        if not thumbnail_path.is_file():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(thumbnail_path, self.root / "thumbnail.png")
        logger.info("Topic cache: thumbnail saved for %s", self.key)

    def try_restore_thumbnail(self, output_path: Path = THUMBNAIL_PATH) -> bool:
        cached = self.root / "thumbnail.png"
        if not cached.is_file():
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, output_path)
        logger.info("Topic cache: thumbnail restored for %s", self.key)
        return True
