"""Video-first visual timeline: Pexels videos → Pexels images → Pixabay → single output."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import requests

from agents.subtitle_config import build_subtitle_force_style
from agents.timeline_video_builder import (
    FFMPEG_TIMEOUT_BUFFER,
    MOTION_EFFECTS,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    build_motion_filter,
    escape_subtitles_path,
    probe_duration,
    resolve_ffmpeg_tool,
)
from agents.visual_asset_agent import (
    APIKeyMissingError,
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
    REQUEST_TIMEOUT,
    SearchCache,
    PexelsClient,
    PixabayClient,
    keywords_from_description,
)

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SCENES_PATH = Path("scenes/scenes.json")
TIMELINE_ASSETS_DIR = Path("assets/timeline")
AUDIO_PATH = Path("audio/output.wav")
CAPTIONS_PATH = Path("captions/output.srt")
OUTPUT_PATH = Path("videos/output.mp4")
VIDEOS_DIR = Path("videos")

PEXELS_VIDEOS_SEARCH_URL = "https://api.pexels.com/v1/videos/search"
MIN_VIDEO_WIDTH = 720
MIN_VIDEO_HEIGHT = 1080
MIN_VIDEO_DURATION = 3
MIN_SEGMENT_SECONDS = 2.0
PROGRESS_STEPS = 8
DEFAULT_FFMPEG = "ffmpeg"
DEFAULT_FFPROBE = "ffprobe"

AssetKind = Literal["video", "image"]
SourceKind = Literal["pexels_video", "pexels_image", "pixabay_image"]


class VisualTimelineAgentError(Exception):
    """Base error for visual timeline generation."""


class ScenesNotFoundError(VisualTimelineAgentError):
    """scenes/scenes.json is missing or invalid."""


class NarrationNotFoundError(VisualTimelineAgentError):
    """Narration audio is missing."""


class CaptionsNotFoundError(VisualTimelineAgentError):
    """Captions file is missing."""


class FFmpegNotFoundError(VisualTimelineAgentError):
    """FFmpeg or ffprobe is not available."""


class TimelineAssetError(VisualTimelineAgentError):
    """Failed to acquire or render a timeline asset."""


class TimelineRenderError(VisualTimelineAgentError):
    """FFmpeg failed during timeline rendering."""


@dataclass(frozen=True)
class VideoCandidate:
    """A remote stock video suitable for a scene segment."""

    url: str
    width: int
    height: int
    duration: float
    source: str = "pexels_video"
    photographer: str = ""

    @property
    def is_portrait(self) -> bool:
        return self.height >= self.width

    @property
    def meets_minimum(self) -> bool:
        return (
            self.width >= MIN_VIDEO_WIDTH
            and self.height >= MIN_VIDEO_HEIGHT
            and self.duration >= MIN_VIDEO_DURATION
        )

    def score(self) -> float:
        score = float(self.width * self.height)
        if self.is_portrait:
            score *= 1.3
        if self.height >= 1920 and self.width >= 1080:
            score *= 1.15
        if self.duration >= 8:
            score *= 1.05
        return score


@dataclass
class SceneRecord:
    scene_number: int
    title: str
    visual_description: str
    duration_seconds: float
    query: str = ""
    asset_kind: AssetKind | None = None
    source: SourceKind | None = None
    asset_path: Path | None = None
    motion_effect: str | None = None
    pending_url: str | None = None
    pending_ext: str | None = None


@dataclass
class TimelineBuildResult:
    output_path: Path
    scene_count: int
    video_scenes: int
    image_scenes: int
    narration_seconds: float
    final_seconds: float


class AssetFileCache:
    """Persist downloaded scene assets to avoid redundant downloads."""

    def __init__(self, assets_dir: Path = TIMELINE_ASSETS_DIR) -> None:
        self.assets_dir = assets_dir
        self.meta_path = assets_dir / "manifest.json"

    def _load_manifest(self) -> dict[str, Any]:
        if not self.meta_path.is_file():
            return {}
        try:
            data = json.loads(self.meta_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def get_cached_path(
        self,
        scene_number: int,
        url: str,
        extension: str,
    ) -> Path | None:
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        manifest = self._load_manifest()
        key = str(scene_number)
        entry = manifest.get(key)
        if not isinstance(entry, dict):
            return None
        if entry.get("url_hash") != digest:
            return None
        path = self.assets_dir / f"scene_{scene_number}{extension}"
        if path.is_file() and path.stat().st_size > 10_000:
            logger.debug("Asset cache hit for scene %d", scene_number)
            return path
        return None

    def record(self, scene_number: int, url: str, path: Path, kind: AssetKind, source: str) -> None:
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        manifest = self._load_manifest()
        manifest[str(scene_number)] = {
            "url_hash": digest,
            "path": path.name,
            "kind": kind,
            "source": source,
            "cached_at": time.time(),
        }
        self._save_manifest(manifest)


class PexelsVideoClient:
    """Search portrait stock videos on Pexels."""

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

    def search(self, query: str, per_page: int = 15) -> list[VideoCandidate]:
        self._require_key()
        cached = self.cache.get("pexels_video", query)
        if cached is not None:
            logger.info("Pexels video cache hit for query: %s", query)
            return [self._from_cache(item) for item in cached if item]

        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "portrait",
        }
        try:
            response = self.session.get(
                PEXELS_VIDEOS_SEARCH_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.error("Pexels video search failed for '%s': %s", query, exc)
            return []

        videos = data.get("videos") or []
        candidates: list[VideoCandidate] = []
        cache_payload: list[dict[str, Any]] = []

        for video in videos:
            if not isinstance(video, dict):
                continue
            duration = float(video.get("duration") or 0)
            if duration < MIN_VIDEO_DURATION:
                continue
            best = self._best_video_file(video.get("video_files") or [])
            if best is None:
                continue
            url, width, height = best
            if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
                continue
            user = video.get("user") or {}
            candidate = VideoCandidate(
                url=url,
                width=width,
                height=height,
                duration=duration,
                photographer=str(user.get("name") or ""),
            )
            candidates.append(candidate)
            cache_payload.append(
                {
                    "url": url,
                    "width": width,
                    "height": height,
                    "duration": duration,
                    "source": "pexels_video",
                    "photographer": candidate.photographer,
                }
            )

        self.cache.set("pexels_video", query, cache_payload)
        candidates.sort(key=lambda c: c.score(), reverse=True)
        logger.info("Pexels videos returned %d matches for: %s", len(candidates), query)
        return candidates

    @staticmethod
    def _best_video_file(files: list[Any]) -> tuple[str, int, int] | None:
        mp4_files: list[tuple[str, int, int, int]] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            if str(item.get("file_type") or "").lower() != "video/mp4":
                continue
            link = str(item.get("link") or "").strip()
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            if not link or width <= 0 or height <= 0:
                continue
            mp4_files.append((link, width, height, width * height))

        if not mp4_files:
            return None
        mp4_files.sort(key=lambda row: (row[3], row[2]), reverse=True)
        link, width, height, _ = mp4_files[0]
        return link, width, height

    @staticmethod
    def _from_cache(item: dict[str, Any]) -> VideoCandidate:
        return VideoCandidate(
            url=str(item["url"]),
            width=int(item["width"]),
            height=int(item["height"]),
            duration=float(item.get("duration") or MIN_VIDEO_DURATION),
            photographer=str(item.get("photographer") or ""),
        )


class VisualTimelineAgent:
    """
    Video-first pipeline: search stock video → image fallbacks, build one timeline,
    render a single videos/output.mp4 with narration and captions.
    """

    def __init__(
        self,
        scenes_path: Path | str = SCENES_PATH,
        assets_dir: Path | str = TIMELINE_ASSETS_DIR,
        audio_path: Path | str = AUDIO_PATH,
        captions_path: Path | str = CAPTIONS_PATH,
        output_path: Path | str = OUTPUT_PATH,
        cache_dir: Path | str = CACHE_DIR,
        ffmpeg: str | None = None,
        ffprobe: str | None = None,
        pexels_video: PexelsVideoClient | None = None,
        pexels_images: PexelsClient | None = None,
        pixabay: PixabayClient | None = None,
    ) -> None:
        self.scenes_path = Path(scenes_path)
        self.assets_dir = Path(assets_dir)
        self.audio_path = Path(audio_path)
        self.captions_path = Path(captions_path)
        self.output_path = Path(output_path)
        self.ffmpeg = resolve_ffmpeg_tool(ffmpeg or DEFAULT_FFMPEG, "FFMPEG_EXECUTABLE")
        self.ffprobe = resolve_ffmpeg_tool(ffprobe or DEFAULT_FFPROBE, "FFPROBE_EXECUTABLE")
        self.search_cache = SearchCache(Path(cache_dir), CACHE_TTL_SECONDS)
        self.file_cache = AssetFileCache(self.assets_dir)
        self.pexels_video = pexels_video or PexelsVideoClient(cache=self.search_cache)
        self.pexels_images = pexels_images or PexelsClient(cache=self.search_cache)
        self.pixabay = pixabay or PixabayClient(cache=self.search_cache)
        self._scenes: list[SceneRecord] = []
        self._narration_seconds = 0.0
        self._temp_dir: Path | None = None

    def generate(self) -> TimelineBuildResult:
        """Build one final Short from scenes.json with video-first visuals."""
        if not self._has_any_api_key():
            raise APIKeyMissingError(
                "No API keys configured. Set PEXELS_API_KEY and/or PIXABAY_API_KEY in .env"
            )

        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.search_cache.cache_dir.mkdir(parents=True, exist_ok=True)
        self._verify_ffmpeg()

        self._print_progress(1, "Reading scenes...")
        self._read_scenes()
        self._narration_seconds = self._read_narration_duration()
        self._normalize_durations()

        self._print_progress(2, "Searching Pexels Videos...")
        self._search_pexels_videos()

        self._print_progress(3, "Searching Images...")
        self._search_pexels_images()
        self._search_pixabay_images()
        self._download_assets()

        self._print_progress(4, "Building timeline...")
        missing = [s for s in self._scenes if s.asset_path is None]
        if missing:
            numbers = ", ".join(str(s.scene_number) for s in missing)
            raise TimelineAssetError(
                f"No visual asset found for scene(s): {numbers}. "
                "Check API keys and scene descriptions."
            )
        self._assign_motion_effects()

        self._temp_dir = Path(tempfile.mkdtemp(prefix="yt_visual_timeline_"))
        try:
            self._print_progress(5, "Applying motion...")
            segment_paths = self._render_timeline_segments()

            visual_path = self._concat_segments(segment_paths)

            self._print_progress(6, "Adding narration...")
            self._print_progress(7, "Adding captions...")
            self._finalize_with_audio_and_subtitles(visual_path)

            self._print_progress(8, "Completed")
            self._verify_output()
            final_seconds = probe_duration(self.output_path, self.ffprobe)
            result = TimelineBuildResult(
                output_path=self.output_path.resolve(),
                scene_count=len(self._scenes),
                video_scenes=sum(1 for s in self._scenes if s.asset_kind == "video"),
                image_scenes=sum(1 for s in self._scenes if s.asset_kind == "image"),
                narration_seconds=self._narration_seconds,
                final_seconds=final_seconds,
            )
            self._print_summary(result)
            return result
        finally:
            if self._temp_dir and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.debug("Removed temp visual timeline directory")

    def _has_any_api_key(self) -> bool:
        return bool(
            self.pexels_video.api_key
            or self.pexels_images.api_key
            or self.pixabay.api_key
        )

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _verify_ffmpeg(self) -> None:
        for tool in (self.ffmpeg, self.ffprobe):
            if shutil.which(tool) is None and not Path(tool).is_file():
                raise FFmpegNotFoundError(f"{tool} not found on PATH.")
        logger.info("FFmpeg: %s", self.ffmpeg)
        logger.info("FFprobe: %s", self.ffprobe)

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
            try:
                duration = float(item.get("duration_seconds") or 5)
            except (TypeError, ValueError):
                duration = 5.0
            duration = max(MIN_SEGMENT_SECONDS, duration)
            query = keywords_from_description(visual_description, title)
            self._scenes.append(
                SceneRecord(
                    scene_number=scene_number,
                    title=title,
                    visual_description=visual_description,
                    duration_seconds=duration,
                    query=query,
                )
            )

        self._scenes.sort(key=lambda s: s.scene_number)
        if not self._scenes:
            raise ScenesNotFoundError("No valid scenes found in scenes.json.")

        logger.info("Loaded %d scenes from %s", len(self._scenes), self.scenes_path)
        for scene in self._scenes:
            print(
                f"  Scene {scene.scene_number}: {scene.title} "
                f"({scene.duration_seconds:.1f}s) — {scene.query}",
                flush=True,
            )

    def _read_narration_duration(self) -> float:
        if not self.audio_path.is_file():
            raise NarrationNotFoundError(
                f"Narration not found: {self.audio_path}. Run Phase 2 first."
            )
        duration = probe_duration(self.audio_path, self.ffprobe)
        logger.info("Narration duration: %.2f seconds", duration)
        print(f"  Narration length: {duration:.1f}s", flush=True)
        return duration

    def _normalize_durations(self) -> None:
        """Scale per-scene durations to match narration length."""
        total = sum(s.duration_seconds for s in self._scenes)
        if total <= 0:
            per_scene = self._narration_seconds / len(self._scenes)
            for scene in self._scenes:
                scene.duration_seconds = max(MIN_SEGMENT_SECONDS, per_scene)
            return

        ratio = self._narration_seconds / total
        for scene in self._scenes:
            scene.duration_seconds = max(
                MIN_SEGMENT_SECONDS,
                scene.duration_seconds * ratio,
            )

        adjusted = sum(s.duration_seconds for s in self._scenes)
        drift = self._narration_seconds - adjusted
        if self._scenes and abs(drift) > 0.05:
            self._scenes[-1].duration_seconds = max(
                MIN_SEGMENT_SECONDS,
                self._scenes[-1].duration_seconds + drift,
            )

        logger.info(
            "Timeline durations normalized to %.2fs across %d scenes",
            self._narration_seconds,
            len(self._scenes),
        )
        per_avg = self._narration_seconds / len(self._scenes)
        print(
            f"  {len(self._scenes)} scenes × ~{per_avg:.1f}s ≈ {self._narration_seconds:.1f}s",
            flush=True,
        )

    def _search_pexels_videos(self) -> None:
        if not self.pexels_video.api_key:
            logger.warning("PEXELS_API_KEY not set; skipping Pexels video search.")
            return

        for scene in self._scenes:
            if scene.pending_url:
                continue
            candidates = self.pexels_video.search(scene.query)
            if not candidates:
                logger.info("Scene %d: no Pexels video match", scene.scene_number)
                continue
            best = candidates[0]
            scene.asset_kind = "video"
            scene.source = "pexels_video"
            scene.pending_url = best.url
            scene.pending_ext = ".mp4"
            logger.info("Scene %d: Pexels video selected", scene.scene_number)

    def _search_pexels_images(self) -> None:
        if not self.pexels_images.api_key:
            logger.warning("PEXELS_API_KEY not set; skipping Pexels image search.")
            return

        for scene in self._scenes:
            if scene.pending_url:
                continue
            candidates = self.pexels_images.search(scene.query)
            if not candidates:
                continue
            best = candidates[0]
            scene.asset_kind = "image"
            scene.source = "pexels_image"
            scene.pending_url = best.url
            scene.pending_ext = ".jpg"
            logger.info("Scene %d: Pexels image selected", scene.scene_number)

    def _search_pixabay_images(self) -> None:
        if not self.pixabay.api_key:
            logger.warning("PIXABAY_API_KEY not set; skipping Pixabay image search.")
            return

        for scene in self._scenes:
            if scene.pending_url:
                continue
            candidates = self.pixabay.search(scene.query)
            if not candidates:
                continue
            best = candidates[0]
            scene.asset_kind = "image"
            scene.source = "pixabay_image"
            scene.pending_url = best.url
            scene.pending_ext = ".jpg"
            logger.info("Scene %d: Pixabay image selected", scene.scene_number)

    def _download_assets(self) -> None:
        session = requests.Session()
        session.headers["User-Agent"] = "YT-Agent/1.0 (visual-timeline-agent)"

        for scene in self._scenes:
            url = scene.pending_url
            ext = scene.pending_ext
            if not url or not ext or not scene.asset_kind:
                continue

            cached = self.file_cache.get_cached_path(scene.scene_number, url, ext)
            if cached:
                scene.asset_path = cached
                logger.info("Scene %d: using cached %s", scene.scene_number, cached.name)
                continue

            dest = self.assets_dir / f"scene_{scene.scene_number}{ext}"
            try:
                self._download_file(session, url, dest)
                if scene.asset_kind == "image":
                    self._verify_image(dest)
                scene.asset_path = dest
                self.file_cache.record(
                    scene.scene_number,
                    url,
                    dest,
                    scene.asset_kind,
                    scene.source or "unknown",
                )
                logger.info(
                    "Scene %d downloaded (%s) -> %s",
                    scene.scene_number,
                    scene.source,
                    dest,
                )
            except (TimelineAssetError, OSError) as exc:
                logger.error("Scene %d download failed: %s", scene.scene_number, exc)
                scene.asset_path = None
                scene.asset_kind = None
                scene.source = None

    def _download_file(self, session: requests.Session, url: str, output_path: Path) -> None:
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            content = response.content
        except requests.RequestException as exc:
            raise TimelineAssetError(f"Download failed: {exc}") from exc

        min_size = 50_000 if output_path.suffix.lower() in (".jpg", ".jpeg") else 100_000
        if len(content) < min_size:
            raise TimelineAssetError(
                f"Downloaded file too small ({len(content)} bytes)."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

    def _verify_image(self, path: Path) -> None:
        try:
            from PIL import Image
        except ImportError as exc:
            raise VisualTimelineAgentError(
                "Pillow is required for image verification. Run: pip install Pillow"
            ) from exc

        with Image.open(path) as img:
            width, height = img.size
            if img.format and img.format.upper() not in ("JPEG", "JPG"):
                img.convert("RGB").save(path, "JPEG", quality=92)
        if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
            path.unlink(missing_ok=True)
            raise TimelineAssetError(
                f"Image {width}x{height} below minimum {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}"
            )

    def _assign_motion_effects(self) -> None:
        for scene in self._scenes:
            if scene.asset_kind == "image":
                scene.motion_effect = random.choice(MOTION_EFFECTS)
                logger.info(
                    "Scene %d image motion: %s (%.2fs)",
                    scene.scene_number,
                    scene.motion_effect,
                    scene.duration_seconds,
                )

    def _render_timeline_segments(self) -> list[Path]:
        assert self._temp_dir is not None
        segment_paths: list[Path] = []

        for scene in self._scenes:
            assert scene.asset_path is not None
            segment_path = self._temp_dir / f"seg_{scene.scene_number:03d}.mp4"
            if scene.asset_kind == "video":
                self._render_video_segment(scene, segment_path)
            else:
                self._render_image_segment(scene, segment_path)
            segment_paths.append(segment_path)

        return segment_paths

    def _render_video_segment(self, scene: SceneRecord, output_path: Path) -> None:
        assert scene.asset_path is not None
        w, h, fps = VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},"
            f"setsar=1,fps={fps}"
        )
        command = [
            self.ffmpeg,
            "-y",
            "-i",
            str(scene.asset_path.resolve()),
            "-vf",
            vf,
            "-t",
            str(scene.duration_seconds),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
        logger.info(
            "Trimming scene %d video to %.2fs: %s",
            scene.scene_number,
            scene.duration_seconds,
            scene.asset_path.name,
        )
        self._run_ffmpeg(command, f"video segment {scene.scene_number}")

    def _render_image_segment(self, scene: SceneRecord, output_path: Path) -> None:
        assert scene.asset_path is not None
        effect = scene.motion_effect or random.choice(MOTION_EFFECTS)
        frames = max(1, int(round(scene.duration_seconds * VIDEO_FPS)))
        filter_chain = build_motion_filter(effect, frames)
        command = [
            self.ffmpeg,
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(VIDEO_FPS),
            "-i",
            str(scene.asset_path.resolve()),
            "-vf",
            filter_chain,
            "-t",
            str(scene.duration_seconds),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output_path),
        ]
        logger.info(
            "Rendering scene %d image (%s, %.2fs)",
            scene.scene_number,
            effect,
            scene.duration_seconds,
        )
        self._run_ffmpeg(command, f"image segment {scene.scene_number}")

    def _concat_segments(self, segment_paths: list[Path]) -> Path:
        assert self._temp_dir is not None
        concat_list = self._temp_dir / "concat.txt"
        lines = [f"file '{path.resolve().as_posix()}'" for path in segment_paths]
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

        visual_path = self._temp_dir / "visual_timeline.mp4"
        command = [
            self.ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(VIDEO_FPS),
            str(visual_path),
        ]
        self._run_ffmpeg(command, "concat visual timeline")
        logger.info("Visual timeline built: %s", visual_path)
        return visual_path

    def _finalize_with_audio_and_subtitles(self, visual_path: Path) -> None:
        if not self.captions_path.is_file():
            raise CaptionsNotFoundError(
                f"Captions not found: {self.captions_path}. Run Phase 3 first."
            )
        if self.output_path.exists():
            self.output_path.unlink()

        subtitles = escape_subtitles_path(self.captions_path)
        force_style = build_subtitle_force_style()
        video_filter = f"subtitles={subtitles}:force_style='{force_style}'"
        command = [
            self.ffmpeg,
            "-y",
            "-i",
            str(visual_path.resolve()),
            "-i",
            str(self.audio_path.resolve()),
            "-vf",
            video_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-r",
            str(VIDEO_FPS),
            "-shortest",
            str(self.output_path.resolve()),
        ]
        self._run_ffmpeg(command, "final video with narration and captions")

    def _run_ffmpeg(self, command: list[str], label: str) -> None:
        timeout = max(120, int(self._narration_seconds) + FFMPEG_TIMEOUT_BUFFER)
        logger.debug("FFmpeg (%s): %s", label, " ".join(command))
        started = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimelineRenderError(f"FFmpeg timed out during {label}") from exc
        except OSError as exc:
            raise TimelineRenderError(f"Failed to run FFmpeg for {label}: {exc}") from exc

        elapsed = time.perf_counter() - started
        logger.info(
            "FFmpeg %s completed in %.1fs (code %s)",
            label,
            elapsed,
            result.returncode,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise TimelineRenderError(
                f"FFmpeg failed during {label}.\n  stderr: {stderr or '(empty)'}"
            )

    def _verify_output(self) -> None:
        if not self.output_path.is_file():
            raise TimelineRenderError(f"Output video was not created: {self.output_path}")
        if self.output_path.stat().st_size == 0:
            raise TimelineRenderError(f"Output video is empty: {self.output_path}")

    def _print_summary(self, result: TimelineBuildResult) -> None:
        print("\nVisual timeline summary:", flush=True)
        print(f"  Scenes: {result.scene_count}", flush=True)
        print(f"  Stock videos: {result.video_scenes}", flush=True)
        print(f"  Stock images (with motion): {result.image_scenes}", flush=True)
        print(f"  Narration: {result.narration_seconds:.1f}s", flush=True)
        print(f"  Final duration: {result.final_seconds:.1f}s", flush=True)
        print(f"  Output: {result.output_path}", flush=True)
        for scene in self._scenes:
            kind = scene.asset_kind or "?"
            source = scene.source or "?"
            motion = f", {scene.motion_effect}" if scene.motion_effect else ""
            print(
                f"    Scene {scene.scene_number}: {kind} ({source}) "
                f"{scene.duration_seconds:.1f}s{motion}",
                flush=True,
            )
