"""Phase 5: Generate YouTube thumbnail from title, scene visuals, or video frame."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
TITLE_PATH = Path("scripts/title.txt")
SCENES_DIR = Path("assets/scenes")
TIMELINE_DIR = Path("assets/timeline")
CLIPS_DIR = Path("assets/clips")
VIDEO_PATH = Path("videos/output.mp4")
THUMBNAILS_DIR = Path("thumbnails")
OUTPUT_PATH = THUMBNAILS_DIR / "output.png"

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720
PROGRESS_STEPS = 6
MAX_THUMBNAIL_WORDS = 4
MAX_THUMBNAIL_LINES = 2
DEFAULT_FFMPEG = "ffmpeg"

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


def resolve_ffmpeg() -> str:
    env_path = os.environ.get("FFMPEG_EXECUTABLE")
    if env_path and Path(env_path).is_file():
        return str(Path(env_path).resolve())
    path = shutil.which(DEFAULT_FFMPEG)
    return path if path else DEFAULT_FFMPEG


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise ThumbnailRenderError(
            "Pillow is required for thumbnails. Run: pip install Pillow"
        ) from exc
    return Image, ImageDraw, ImageFont


class ThumbnailAgent:
    """Build a 1280×720 YouTube thumbnail with bold overlaid text."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        title_path: Path | str = TITLE_PATH,
        output_path: Path | str = OUTPUT_PATH,
        scenes_dir: Path | str = SCENES_DIR,
        clips_dir: Path | str = CLIPS_DIR,
        video_path: Path | str = VIDEO_PATH,
    ) -> None:
        self.model = model
        self.title_path = Path(title_path)
        self.output_path = Path(output_path)
        self.scenes_dir = Path(scenes_dir)
        self.timeline_dir = TIMELINE_DIR
        self.clips_dir = Path(clips_dir)
        self.video_path = Path(video_path)
        self.ffmpeg = resolve_ffmpeg()
        self._title = ""
        self._text = ThumbnailText("", "")
        self._background_path: Path | None = None

    def generate(self) -> ThumbnailResult:
        """Create thumbnails/output.png from title and best available visual."""
        THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

        self._print_progress(1, "Reading title...")
        self._title = self._read_title()
        self._text = self._generate_thumbnail_text(self._title)
        logger.info("Thumbnail text: %s / %s", self._text.line1, self._text.line2)

        self._print_progress(2, "Selecting visual...")
        self._background_path = self._select_visual()
        logger.info("Visual source: %s", self._background_path)

        self._print_progress(3, "Creating layout...")
        canvas = self._build_canvas(self._background_path)

        self._print_progress(4, "Rendering text...")
        composed = self._render_text(canvas, self._text)

        self._print_progress(5, "Saving thumbnail...")
        self._save_thumbnail(composed)

        self._print_progress(6, "Completed")
        self._verify_output()
        result = ThumbnailResult(
            output_path=self.output_path.resolve(),
            title=self._title,
            text=self._text,
            visual_source=str(self._background_path),
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

    def _select_visual(self) -> Path:
        image = self._best_image_in_dirs(
            [self.scenes_dir, self.timeline_dir],
            label="scene images",
        )
        if image:
            print(f"  Using scene image: {image.name}", flush=True)
            return image

        clip_image = self._best_image_in_dirs([self.clips_dir], label="clips")
        if clip_image:
            print(f"  Using clip image: {clip_image.name}", flush=True)
            return clip_image

        clip_video = self._best_video_in_dir(self.clips_dir)
        if clip_video:
            print(f"  Extracting frame from clip: {clip_video.name}", flush=True)
            return self._extract_video_frame(clip_video)

        if self.video_path.is_file() and self.video_path.stat().st_size > 0:
            print(f"  Extracting frame from: {self.video_path.name}", flush=True)
            return self._extract_video_frame(self.video_path)

        raise VisualSourceNotFoundError(
            "No visual source found. Expected images in assets/scenes/ or "
            "assets/timeline/, assets/clips/, or videos/output.mp4."
        )

    def _best_image_in_dirs(
        self,
        directories: list[Path],
        label: str,
    ) -> Path | None:
        best: tuple[int, Path] | None = None
        for directory in directories:
            if not directory.is_dir():
                continue
            for path in directory.iterdir():
                if not path.is_file():
                    continue
                if path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                score = self._image_quality_score(path)
                if score <= 0:
                    continue
                if best is None or score > best[0]:
                    best = (score, path)
        if best:
            logger.info("Best %s: %s (score %d)", label, best[1].name, best[0])
        return best[1] if best else None

    def _image_quality_score(self, path: Path) -> int:
        Image, _, _ = _require_pillow()
        try:
            with Image.open(path) as img:
                width, height = img.size
                pixels = width * height
                if pixels < 640 * 360:
                    return 0
                portrait_bonus = 1_000_000 if height > width else 0
                return pixels + portrait_bonus
        except OSError as exc:
            logger.debug("Skipping unreadable image %s: %s", path, exc)
            return 0

    def _best_video_in_dir(self, directory: Path) -> Path | None:
        if not directory.is_dir():
            return None
        videos = [
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        ]
        if not videos:
            return None
        videos.sort(key=lambda p: p.stat().st_size, reverse=True)
        return videos[0]

    def _extract_video_frame(self, video_path: Path) -> Path:
        if shutil.which(self.ffmpeg) is None and not Path(self.ffmpeg).is_file():
            raise FFmpegNotFoundError(
                "FFmpeg not found. Install FFmpeg to extract a thumbnail frame."
            )

        temp_dir = Path(tempfile.mkdtemp(prefix="yt_thumb_frame_"))
        frame_path = temp_dir / "frame.jpg"
        timestamp = self._pick_frame_timestamp(video_path)

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
            str(frame_path),
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
            raise ThumbnailRenderError(f"Failed to run FFmpeg: {exc}") from exc

        if result.returncode != 0 or not frame_path.is_file():
            stderr = (result.stderr or "").strip()
            raise ThumbnailRenderError(
                f"FFmpeg frame extraction failed: {stderr or 'unknown error'}"
            )
        logger.info("Extracted frame at %.2fs from %s", timestamp, video_path.name)
        return frame_path

    def _pick_frame_timestamp(self, video_path: Path) -> float:
        try:
            from agents.timeline_video_builder import probe_duration, resolve_ffmpeg_tool

            ffprobe = resolve_ffmpeg_tool("ffprobe", "FFPROBE_EXECUTABLE")
            duration = probe_duration(video_path, ffprobe)
            return max(0.5, min(duration * 0.35, duration - 0.5))
        except Exception:
            return 1.0

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
        Image, ImageDraw, ImageFont = _require_pillow()
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
        print(f"  Visual: {result.visual_source}", flush=True)
        print(f"  Output: {result.output_path}", flush=True)
