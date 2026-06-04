"""Phase 5: Generate YouTube thumbnail aligned with the final video output."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import ollama
import requests

from agents.visual_asset_agent import (
    ImageCandidate,
    PexelsClient,
    PixabayClient,
    SearchCache,
    keywords_from_description,
    landscape_image_score,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
TITLE_PATH = Path("scripts/title.txt")
SCENES_PATH = Path("scenes/scenes.json")
TIMELINE_DIR = Path("assets/timeline")
VIDEO_PATH = Path("videos/output.mp4")
THUMBNAILS_DIR = Path("thumbnails")
OUTPUT_PATH = THUMBNAILS_DIR / "output.png"

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720
PROGRESS_STEPS = 7
MAX_THUMBNAIL_WORDS = 4
MAX_THUMBNAIL_LINES = 2
DEFAULT_FFMPEG = "ffmpeg"

FRAME_SAMPLE_COUNT = 8
MIN_FRAME_SCORE = 0.38
THUMB_MIN_WIDTH = 1280
THUMB_MIN_HEIGHT = 720
STOCK_DOWNLOAD_TIMEOUT = 45

SOURCE_VIDEO_FRAME = "Video Frame"
SOURCE_PEXELS = "Pexels"
SOURCE_PIXABAY = "Pixabay"
SOURCE_AI = "AI"

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm", ".mkv"})

THUMBNAIL_TEXT_SYSTEM = """You write bold YouTube thumbnail text.
Rules:
- Output exactly 2 lines
- Line 1: 1-2 words, ALL CAPS
- Line 2: 1-2 words, ALL CAPS
- Maximum 4 words total across both lines
- No quotes, hashtags, punctuation, or extra commentary
- Make it punchy and readable on mobile

Example for title "What Is EBITDA?":
EBITDA
EXPLAINED"""

THUMBNAIL_TEXT_USER = """Video title:
{title}

Write thumbnail text (2 lines, ALL CAPS, max 4 words total)."""

TITLE_FILLER_WORDS = frozenset(
    """
    a an the and or but in on at to for of with by from as is are was were be been
    being have has had do does did will would could should may might must can this
    that these those it its they them their we you your our not no nor so if then
    than when while where who which what how why all each every both few more most
    other some such only own same into over under again further here there once
    mastering key essential guide introduction overview basics explained
    """.split()
)


def extract_ollama_chat_content(response: object) -> str:
    """Read assistant text from ollama.chat() dict or ChatResponse object."""
    if response is None:
        return ""

    if isinstance(response, dict):
        message = response.get("message")
    else:
        message = getattr(response, "message", None)
        if message is None and hasattr(response, "model_dump"):
            try:
                data = response.model_dump()
                message = data.get("message") if isinstance(data, dict) else None
            except Exception:
                message = None

    if message is None:
        return ""

    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)

    text = (content or "").strip() if content is not None else ""
    if text:
        return text

    logger.debug(
        "Ollama message had no content (message type=%s)",
        type(message).__name__,
    )
    return ""


class ThumbnailAgentError(Exception):
    """Base error for thumbnail generation."""


class TitleNotFoundError(ThumbnailAgentError):
    """scripts/title.txt is missing or empty."""


class VisualSourceNotFoundError(ThumbnailAgentError):
    """No suitable image or video source for the thumbnail."""


class FFmpegNotFoundError(ThumbnailAgentError):
    """FFmpeg is required to extract a video frame."""


class ThumbnailRenderError(ThumbnailAgentError):
    """Pillow rendering or save failed."""


@dataclass(frozen=True)
class ThumbnailText:
    line1: str
    line2: str

    @property
    def lines(self) -> tuple[str, str]:
        return (self.line1, self.line2)

    @property
    def word_count(self) -> int:
        return len((f"{self.line1} {self.line2}").split())


@dataclass
class ThumbnailResult:
    output_path: Path
    title: str
    text: ThumbnailText
    visual_source: str
    source_type: str
    frame_score: float | None = None


def resolve_ffmpeg() -> str:
    env_path = os.environ.get("FFMPEG_EXECUTABLE")
    if env_path and Path(env_path).is_file():
        return str(Path(env_path).resolve())
    path = shutil.which(DEFAULT_FFMPEG)
    return path if path else DEFAULT_FFMPEG


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageStat
    except ImportError as exc:
        raise ThumbnailRenderError(
            "Pillow is required for thumbnails. Run: pip install Pillow"
        ) from exc
    return Image, ImageDraw, ImageFont, ImageStat


class ThumbnailAgent:
    """Build a 1280×720 YouTube thumbnail with bold overlaid text."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        title_path: Path | str = TITLE_PATH,
        output_path: Path | str = OUTPUT_PATH,
        scenes_path: Path | str = SCENES_PATH,
        video_path: Path | str = VIDEO_PATH,
        pexels_client: PexelsClient | None = None,
        pixabay_client: PixabayClient | None = None,
    ) -> None:
        self.model = model
        self.title_path = Path(title_path)
        self.output_path = Path(output_path)
        self.scenes_path = Path(scenes_path)
        self.timeline_dir = TIMELINE_DIR
        self.video_path = Path(video_path)
        self.ffmpeg = resolve_ffmpeg()
        cache = SearchCache()
        self.pexels = pexels_client or PexelsClient(cache=cache)
        self.pixabay = pixabay_client or PixabayClient(cache=cache)
        self._title = ""
        self._text = ThumbnailText("", "")
        self._background_path: Path | None = None
        self._source_type = ""
        self._frame_score: float | None = None
        self._frame_temp_dir: Path | None = None

    def generate(self) -> ThumbnailResult:
        """Create thumbnails/output.png from title and best available visual."""
        THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

        self._print_progress(1, "Reading title...")
        self._title = self._read_title()
        self._text = self._generate_thumbnail_text(self._title)
        logger.info("Thumbnail text: %s / %s", self._text.line1, self._text.line2)

        self._print_progress(2, "Analyzing video & selecting visual...")
        self._background_path, self._source_type, self._frame_score = self._select_visual()
        logger.info("Thumbnail Source: %s", self._source_type)
        logger.info("Background file: %s", self._background_path)
        if self._frame_score is not None:
            logger.info("Best frame score: %.3f", self._frame_score)

        self._print_progress(3, "Creating layout...")
        canvas = self._build_canvas(self._background_path)

        self._print_progress(4, "Rendering text...")
        composed = self._render_text(canvas, self._text)

        self._print_progress(5, "Saving thumbnail...")
        self._save_thumbnail(composed)

        self._print_progress(6, "Completed")
        self._verify_output()
        self._cleanup_frame_temp_dir()
        result = ThumbnailResult(
            output_path=self.output_path.resolve(),
            title=self._title,
            text=self._text,
            visual_source=str(self._background_path),
            source_type=self._source_type,
            frame_score=self._frame_score,
        )
        self._print_summary(result)
        return result

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _read_title(self) -> str:
        if not self.title_path.is_file():
            raise TitleNotFoundError(
                f"Title file not found: {self.title_path}. Run Phase 1 metadata first."
            )
        title = self.title_path.read_text(encoding="utf-8").strip()
        if not title:
            raise TitleNotFoundError(f"Title file is empty: {self.title_path}")
        print(f"  Title: {title}", flush=True)
        return title

    def _generate_thumbnail_text(self, title: str) -> ThumbnailText:
        try:
            raw = self._chat_thumbnail_text(title)
            if raw:
                text = self._parse_thumbnail_text(raw)
                self._validate_thumbnail_text(text)
                return text
            logger.warning("Ollama returned empty thumbnail text; using fallback")
        except ThumbnailAgentError as exc:
            logger.warning("%s; using fallback thumbnail text", exc)
        except Exception as exc:
            logger.warning("Ollama thumbnail text failed (%s); using fallback", exc)
        return self._fallback_thumbnail_text(title)

    def _chat_thumbnail_text(self, title: str) -> str:
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": THUMBNAIL_TEXT_SYSTEM},
                    {
                        "role": "user",
                        "content": THUMBNAIL_TEXT_USER.format(title=title),
                    },
                ],
            )
        except Exception as exc:
            err = str(exc).lower()
            if "connection" in err or "refused" in err or "connect" in err:
                raise ThumbnailAgentError(
                    "Ollama is not running. Start Ollama or rely on fallback text."
                ) from exc
            raise ThumbnailAgentError(f"Ollama request failed: {exc}") from exc

        content = extract_ollama_chat_content(response)
        if content:
            logger.info("Ollama thumbnail text: %r", content.replace("\n", " / "))
        return content

    def _parse_thumbnail_text(self, raw: str) -> ThumbnailText:
        lines = [
            re.sub(r"[^A-Za-z0-9\s]", "", line).strip().upper()
            for line in raw.strip().splitlines()
            if line.strip()
        ]
        lines = [line for line in lines if line]
        if len(lines) >= 2:
            return ThumbnailText(line1=lines[0], line2=lines[1])
        if len(lines) == 1:
            words = lines[0].split()
            if len(words) >= 2:
                return ThumbnailText(line1=words[0], line2=" ".join(words[1:3]))
            return ThumbnailText(line1=words[0], line2="EXPLAINED")
        raise ThumbnailAgentError("Could not parse thumbnail text from model output.")

    def _validate_thumbnail_text(self, text: ThumbnailText) -> None:
        if not text.line1 or not text.line2:
            raise ThumbnailAgentError("Thumbnail text must have two non-empty lines.")
        if text.word_count > MAX_THUMBNAIL_WORDS:
            raise ThumbnailAgentError(
                f"Thumbnail text has {text.word_count} words; max is {MAX_THUMBNAIL_WORDS}."
            )

    @staticmethod
    def _fallback_thumbnail_text(title: str) -> ThumbnailText:
        lower = title.lower()
        if "capital expenditure" in lower or "capex" in lower:
            text = ThumbnailText(line1="CAPEX", line2="EXPLAINED")
        elif "ebitda" in lower:
            text = ThumbnailText(line1="EBITDA", line2="EXPLAINED")
        else:
            cleaned = re.sub(
                r"^(what\s+is|how\s+to|why\s+|the\s+)",
                "",
                title.strip(),
                flags=re.IGNORECASE,
            )
            words = [
                w.upper()
                for w in re.findall(r"[A-Za-z0-9]+", cleaned)
                if w.lower() not in TITLE_FILLER_WORDS
            ]
            if not words:
                words = [
                    w.upper()
                    for w in re.findall(r"[A-Za-z0-9]+", title)
                    if w.lower() not in TITLE_FILLER_WORDS
                ] or ["VIDEO"]

            line1 = words[0]
            line2 = words[-1] if len(words) > 1 and words[-1] != line1 else "GROWTH"
            if line2 in {"KEY", "A", "AN", "THE"} and len(words) > 2:
                line2 = words[-2]
            if line2 == line1:
                line2 = "EXPLAINED"
            text = ThumbnailText(line1=line1[:24], line2=line2[:24])

        logger.info("Using fallback thumbnail text: %s / %s", text.line1, text.line2)
        return text

    def _select_visual(self) -> tuple[Path, str, float | None]:
        """Priority: video frame → Pexels → Pixabay → AI."""
        if self.video_path.is_file() and self.video_path.stat().st_size > 0:
            frame_path, score = self._best_frame_from_video(self.video_path)
            if frame_path and score >= MIN_FRAME_SCORE:
                print(
                    f"  Thumbnail Source: {SOURCE_VIDEO_FRAME} (score {score:.2f})",
                    flush=True,
                )
                return frame_path, SOURCE_VIDEO_FRAME, score
            logger.info(
                "No suitable video frame (best score %.3f < %.2f); trying stock",
                score or 0,
                MIN_FRAME_SCORE,
            )

        query = self._thumbnail_search_query()
        pexels_path = self._fetch_stock_image(self.pexels, query, SOURCE_PEXELS, "landscape")
        if pexels_path:
            return pexels_path, SOURCE_PEXELS, None

        pixabay_path = self._fetch_stock_image(
            self.pixabay, query, SOURCE_PIXABAY, "horizontal"
        )
        if pixabay_path:
            return pixabay_path, SOURCE_PIXABAY, None

        print(f"  Thumbnail Source: {SOURCE_AI} (composed fallback)", flush=True)
        return self._generate_ai_fallback_background(), SOURCE_AI, None

    def _thumbnail_search_query(self) -> str:
        """Build a stock search query aligned with video content."""
        scene_text = ""
        if self.scenes_path.is_file():
            try:
                data = json.loads(self.scenes_path.read_text(encoding="utf-8"))
                scenes = data if isinstance(data, list) else data.get("scenes", [])
                if scenes and isinstance(scenes[0], dict):
                    first = scenes[0]
                    scene_text = (
                        f"{first.get('title', '')} {first.get('visual_description', '')}"
                    )
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug("Could not read scenes for thumbnail query: %s", exc)

        if scene_text.strip():
            return keywords_from_description(scene_text, self._title)
        return keywords_from_description(self._title, self._title)

    def _best_frame_from_video(self, video_path: Path) -> tuple[Path | None, float]:
        """Extract multiple frames and pick the highest-quality candidate."""
        if shutil.which(self.ffmpeg) is None and not Path(self.ffmpeg).is_file():
            logger.warning("FFmpeg not found; skipping video frame analysis")
            return None, 0.0

        self._cleanup_frame_temp_dir()
        self._frame_temp_dir = Path(tempfile.mkdtemp(prefix="yt_thumb_frames_"))
        timestamps = self._sample_frame_timestamps(video_path)
        best_path: Path | None = None
        best_score = 0.0

        for index, timestamp in enumerate(timestamps):
            frame_path = self._frame_temp_dir / f"frame_{index:02d}.jpg"
            if not self._extract_frame_at(video_path, timestamp, frame_path):
                continue
            score = self._score_frame(frame_path)
            logger.info(
                "Frame sample %d @ %.2fs — score %.3f",
                index + 1,
                timestamp,
                score,
            )
            if score > best_score:
                best_score = score
                best_path = frame_path

        if best_path:
            logger.info(
                "Selected best frame from %s (score %.3f)",
                video_path.name,
                best_score,
            )
        return best_path, best_score

    def _sample_frame_timestamps(self, video_path: Path) -> list[float]:
        try:
            from agents.timeline_video_builder import probe_duration, resolve_ffmpeg_tool

            ffprobe = resolve_ffmpeg_tool("ffprobe", "FFPROBE_EXECUTABLE")
            duration = probe_duration(video_path, ffprobe)
        except Exception:
            duration = 30.0

        if duration < 1.0:
            return [0.0]

        start = max(0.5, duration * 0.12)
        end = max(start + 0.5, duration * 0.88)
        count = max(3, FRAME_SAMPLE_COUNT)
        if count == 1 or end <= start:
            return [min(duration * 0.35, duration - 0.1)]

        step = (end - start) / (count - 1)
        return [round(start + step * i, 2) for i in range(count)]

    def _extract_frame_at(self, video_path: Path, timestamp: float, out_path: Path) -> bool:
        command = [
            self.ffmpeg,
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(video_path.resolve()),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except OSError as exc:
            logger.debug("Frame extract failed: %s", exc)
            return False
        return result.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0

    def _score_frame(self, frame_path: Path) -> float:
        """
        Score frame quality: clarity, brightness, visual appeal, subject visibility.
        Returns 0.0–1.0 (higher is better).
        """
        Image, ImageStat, _ = _require_pillow()
        try:
            with Image.open(frame_path) as img:
                rgb = img.convert("RGB")
                thumb = rgb.copy()
                thumb.thumbnail((480, 270))
                gray = thumb.convert("L")
                stat = ImageStat.Stat(thumb)
                gray_stat = ImageStat.Stat(gray)

                r, g, b = stat.mean[:3]
                brightness = 0.299 * r + 0.587 * g + 0.114 * b
                brightness_score = max(0.0, 1.0 - abs(brightness - 125.0) / 125.0)

                contrast = sum(gray_stat.stddev) / max(len(gray_stat.stddev), 1)
                clarity_score = min(contrast / 45.0, 1.0)

                max_c = max(r, g, b)
                min_c = min(r, g, b)
                saturation = (max_c - min_c) / max_c if max_c > 1 else 0.0
                appeal_score = min(saturation * 2.5, 1.0) * 0.5 + clarity_score * 0.5

                w, h = gray.size
                margin_x = int(w * 0.2)
                margin_y = int(h * 0.2)
                center = gray.crop((margin_x, margin_y, w - margin_x, h - margin_y))
                full_std = sum(gray_stat.stddev) / max(len(gray_stat.stddev), 1)
                center_std = sum(ImageStat.Stat(center).stddev) / max(
                    len(ImageStat.Stat(center).stddev), 1
                )
                subject_score = min(center_std / (full_std + 1.0), 1.2) / 1.2

                return (
                    clarity_score * 0.35
                    + brightness_score * 0.25
                    + appeal_score * 0.2
                    + subject_score * 0.2
                )
        except OSError as exc:
            logger.debug("Frame score failed for %s: %s", frame_path, exc)
            return 0.0

    def _fetch_stock_image(
        self,
        client: PexelsClient | PixabayClient,
        query: str,
        source_label: str,
        orientation: str,
    ) -> Path | None:
        api_key = getattr(client, "api_key", "")
        if not api_key:
            logger.warning("%s API key not set; skipping", source_label)
            return None

        try:
            candidates = client.search(query, per_page=12, orientation=orientation)
        except Exception as exc:
            logger.warning("%s search failed: %s", source_label, exc)
            return None

        suitable = [
            c
            for c in candidates
            if c.width >= THUMB_MIN_WIDTH and c.height >= THUMB_MIN_HEIGHT
        ]
        if not suitable:
            suitable = [
                c for c in candidates if c.width >= 960 and c.height >= 540
            ]
        if not suitable:
            logger.info("%s returned no images large enough for thumbnail", source_label)
            return None

        suitable.sort(key=landscape_image_score, reverse=True)
        best = suitable[0]
        path = self._download_stock_image(best, source_label)
        if path:
            print(f"  Thumbnail Source: {source_label} — {best.url[:60]}...", flush=True)
        return path

    def _download_stock_image(self, candidate: ImageCandidate, label: str) -> Path | None:
        temp_dir = Path(tempfile.mkdtemp(prefix="yt_thumb_stock_"))
        ext = ".jpg"
        if ".png" in candidate.url.lower():
            ext = ".png"
        dest = temp_dir / f"stock{ext}"
        try:
            response = requests.get(candidate.url, timeout=STOCK_DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            dest.write_bytes(response.content)
        except requests.RequestException as exc:
            logger.warning("%s download failed: %s", label, exc)
            return None

        Image, _, _ = _require_pillow()
        try:
            with Image.open(dest) as img:
                if img.size[0] < 640 or img.size[1] < 360:
                    logger.warning("Downloaded %s image too small: %s", label, img.size)
                    return None
        except OSError:
            return None
        return dest

    def _generate_ai_fallback_background(self) -> Path:
        """Last resort: clean composed 1280×720 background (logged as AI)."""
        Image, ImageDraw, _ = _require_pillow()
        temp_dir = Path(tempfile.mkdtemp(prefix="yt_thumb_ai_"))
        path = temp_dir / "ai_background.png"

        accent = self._accent_color_from_timeline()
        img = Image.new("RGB", (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), accent)
        draw = ImageDraw.Draw(img)
        for y in range(THUMBNAIL_HEIGHT):
            blend = y / THUMBNAIL_HEIGHT
            shade = int(accent[0] * (1 - blend * 0.55))
            draw.line([(0, y), (THUMBNAIL_WIDTH, y)], fill=(shade, shade, shade))

        cx, cy = THUMBNAIL_WIDTH // 2, THUMBNAIL_HEIGHT // 2
        radius = int(min(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT) * 0.42)
        for r in range(radius, 0, -4):
            alpha = int(28 * (r / radius))
            box = (cx - r, cy - r, cx + r, cy + r)
            draw.ellipse(box, fill=(min(255, accent[0] + alpha),) * 3)

        img.save(path, format="PNG")
        logger.info("AI fallback background composed at %s", path)
        return path

    def _accent_color_from_timeline(self) -> tuple[int, int, int]:
        """Sample average color from timeline assets to stay on-brand with the video."""
        Image, ImageStat, _ = _require_pillow()
        if not self.timeline_dir.is_dir():
            return (22, 22, 26)

        for path in sorted(self.timeline_dir.iterdir()):
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                with Image.open(path) as img:
                    rgb = img.convert("RGB")
                    rgb.thumbnail((160, 90))
                    mean = ImageStat.Stat(rgb).mean[:3]
                    return tuple(int(v * 0.35) for v in mean)
            except OSError:
                continue
        return (22, 22, 26)

    def _cleanup_frame_temp_dir(self) -> None:
        if self._frame_temp_dir and self._frame_temp_dir.is_dir():
            shutil.rmtree(self._frame_temp_dir, ignore_errors=True)
        self._frame_temp_dir = None

    def _build_canvas(self, source: Path) -> object:
        Image, _, _ = _require_pillow()
        try:
            with Image.open(source) as img:
                rgb = img.convert("RGB")
                return self._fit_cover(rgb, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        except OSError as exc:
            raise ThumbnailRenderError(f"Cannot open visual source: {exc}") from exc

    @staticmethod
    def _fit_cover(img: object, width: int, height: int) -> object:
        Image, _, _ = _require_pillow()
        src_w, src_h = img.size
        scale = max(width / src_w, height / src_h)
        resized = img.resize(
            (int(src_w * scale), int(src_h * scale)),
            Image.Resampling.LANCZOS,
        )
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        return resized.crop((left, top, left + width, top + height))

    def _render_text(self, canvas: object, text: ThumbnailText) -> object:
        Image, ImageDraw, ImageFont, _ = _require_pillow()
        base = canvas.copy()
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        bar_height = int(base.height * 0.5)
        bar = Image.new("RGBA", (base.width, bar_height), (0, 0, 0, 150))
        overlay.paste(bar, (0, base.height - bar_height), bar)

        font_large, font_small = self._load_fonts(ImageFont)
        padding = 56
        x = padding
        y = base.height - padding

        lines = [text.line2, text.line1]
        fonts = [font_small, font_large]
        for line, font in zip(lines, fonts):
            bbox = draw.textbbox((0, 0), line, font=font)
            line_h = bbox[3] - bbox[1]
            y -= line_h
            self._draw_stroked_text(draw, (x, y), line, font)
            y -= 18

        composed = Image.alpha_composite(base.convert("RGBA"), overlay)
        return composed.convert("RGB")

    def _load_fonts(self, ImageFont) -> tuple[object, object]:
        size_large = 96
        size_small = 62
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/ARIALBD.TTF",
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/IMPACT.TTF",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        for path in candidates:
            if Path(path).is_file():
                try:
                    return (
                        ImageFont.truetype(path, size_large),
                        ImageFont.truetype(path, size_small),
                    )
                except OSError:
                    continue
        logger.warning("Bold TrueType font not found; using default bitmap font")
        default = ImageFont.load_default()
        return default, default

    @staticmethod
    def _draw_stroked_text(
        draw: object,
        position: tuple[int, int],
        text: str,
        font: object,
    ) -> None:
        x, y = position
        stroke = 6
        shadow = 4
        for dx, dy in (
            (shadow, shadow),
            (shadow + 1, shadow + 1),
        ):
            draw.text(
                (x + dx, y + dy),
                text,
                font=font,
                fill=(0, 0, 0, 160),
            )
        for ox in range(-stroke, stroke + 1):
            for oy in range(-stroke, stroke + 1):
                if ox == 0 and oy == 0:
                    continue
                draw.text((x + ox, y + oy), text, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    def _save_thumbnail(self, image: object) -> None:
        if self.output_path.exists():
            self.output_path.unlink()
        try:
            image.save(self.output_path, format="PNG", optimize=True)
        except OSError as exc:
            raise ThumbnailRenderError(f"Failed to save thumbnail: {exc}") from exc
        logger.info("Thumbnail saved: %s", self.output_path.resolve())

    def _verify_output(self) -> None:
        if not self.output_path.is_file():
            raise ThumbnailRenderError(
                f"Thumbnail was not created: {self.output_path}"
            )
        size = self.output_path.stat().st_size
        if size == 0:
            raise ThumbnailRenderError(f"Thumbnail file is empty: {self.output_path}")

        Image, _, _ = _require_pillow()
        with Image.open(self.output_path) as img:
            dimensions = img.size
            if dimensions != (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT):
                raise ThumbnailRenderError(
                    f"Thumbnail size {dimensions} != "
                    f"({THUMBNAIL_WIDTH}, {THUMBNAIL_HEIGHT})"
                )
        logger.info(
            "Thumbnail verified: %dx%d, %d bytes",
            dimensions[0],
            dimensions[1],
            size,
        )

    def _print_summary(self, result: ThumbnailResult) -> None:
        print("\nThumbnail summary:", flush=True)
        print(f"  Title: {result.title}", flush=True)
        print(f"  Text: {result.text.line1} / {result.text.line2}", flush=True)
        print(f"  Thumbnail Source: {result.source_type}", flush=True)
        if result.frame_score is not None:
            print(f"  Frame score: {result.frame_score:.3f}", flush=True)
        print(f"  Visual: {result.visual_source}", flush=True)
        print(f"  Output: {result.output_path}", flush=True)
