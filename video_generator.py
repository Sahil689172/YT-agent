"""Phase 4: Generate YouTube Shorts video with FFmpeg."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_FFMPEG = "ffmpeg"
DEFAULT_FFPROBE = "ffprobe"
AUDIO_PATH = Path("audio/output.wav")
CAPTIONS_PATH = Path("captions/output.srt")
BACKGROUND_PATH = Path("assets/backgrounds/background.mp4")
OUTPUT_PATH = Path("videos/output.mp4")
ASSETS_DIR = Path("assets")
BACKGROUNDS_DIR = Path("assets/backgrounds")
VIDEOS_DIR = Path("videos")

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
PLACEHOLDER_DURATION_SECONDS = 15
FFMPEG_RENDER_TIMEOUT_BUFFER = 120

from agents.subtitle_config import build_subtitle_force_style

PROGRESS_STEPS = 6


class VideoGeneratorError(Exception):
    """Base error for video generation."""


class AssetNotFoundError(VideoGeneratorError):
    """A required input file is missing."""


class BackgroundNotFoundError(VideoGeneratorError):
    """Background video is missing and could not be created."""


class FFmpegNotFoundError(VideoGeneratorError):
    """FFmpeg or ffprobe is not available."""


class VideoGenerationError(VideoGeneratorError):
    """FFmpeg failed to render the video."""


def resolve_ffmpeg_tool(name: str, env_var: str | None = None) -> str:
    """Resolve ffmpeg or ffprobe from PATH or environment."""
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path and Path(env_path).is_file():
            return str(Path(env_path).resolve())

    path = shutil.which(name)
    if path:
        return path

    return name


def escape_subtitles_path(path: Path) -> str:
    """Escape a path for FFmpeg's subtitles filter (Windows-safe)."""
    try:
        relative = path.resolve().relative_to(Path.cwd())
        escaped = relative.as_posix()
    except ValueError:
        escaped = path.resolve().as_posix()
        if len(escaped) >= 2 and escaped[1] == ":":
            escaped = escaped[0] + "\\:" + escaped[2:]
    escaped = escaped.replace("'", r"\'")
    escaped = escaped.replace("\\", "/")
    return escaped


class VideoGenerator:
    """Build a vertical Short from background video, narration, and burned-in captions."""

    def __init__(
        self,
        ffmpeg: str | None = None,
        ffprobe: str | None = None,
        audio_path: Path | str = AUDIO_PATH,
        captions_path: Path | str = CAPTIONS_PATH,
        background_path: Path | str = BACKGROUND_PATH,
        output_path: Path | str = OUTPUT_PATH,
        width: int = VIDEO_WIDTH,
        height: int = VIDEO_HEIGHT,
        fps: int = VIDEO_FPS,
    ) -> None:
        self.ffmpeg = resolve_ffmpeg_tool(ffmpeg or DEFAULT_FFMPEG, "FFMPEG_EXECUTABLE")
        self.ffprobe = resolve_ffmpeg_tool(ffprobe or DEFAULT_FFPROBE, "FFPROBE_EXECUTABLE")
        self.audio_path = Path(audio_path)
        self.captions_path = Path(captions_path)
        self.background_path = Path(background_path)
        self.output_path = Path(output_path)
        self.width = width
        self.height = height
        self.fps = fps
        self._audio_duration = 0.0
        self._background_duration = 0.0

    def generate(self) -> Path:
        """Render videos/output.mp4 from audio, captions, and background."""
        self._print_progress(1, "Verifying assets...")
        self._ensure_project_dirs()
        self._verify_ffmpeg_tools()
        self._ensure_background_video()
        self._verify_inputs()

        self._print_progress(2, "Reading durations...")
        self._read_durations()

        self._print_progress(3, "Preparing background...")
        self._log_background_preparation()

        self._print_progress(4, "Rendering video...")
        self._render_video()

        self._print_progress(5, "Verifying output...")
        self._verify_output()

        self._print_progress(6, "Completed")
        logger.info("Video saved to %s", self.output_path.resolve())
        return self.output_path.resolve()

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _ensure_project_dirs(self) -> None:
        for directory in (ASSETS_DIR, BACKGROUNDS_DIR, VIDEOS_DIR):
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured directory: %s", directory.resolve())

    def _verify_ffmpeg_tools(self) -> None:
        for tool_name, tool_path in (("ffmpeg", self.ffmpeg), ("ffprobe", self.ffprobe)):
            resolved = shutil.which(tool_path)
            if resolved is None and not Path(tool_path).is_file():
                raise FFmpegNotFoundError(
                    f"{tool_name} not found. Install FFmpeg and add it to PATH."
                )
        logger.info("FFmpeg: %s", self.ffmpeg)
        logger.info("FFprobe: %s", self.ffprobe)

    def _ensure_background_video(self) -> None:
        if self.background_path.is_file() and self.background_path.stat().st_size > 0:
            logger.info("Background video found: %s", self.background_path.resolve())
            return

        logger.warning(
            "Background video missing at %s — creating placeholder",
            self.background_path,
        )
        try:
            self._create_placeholder_background()
        except (OSError, subprocess.SubprocessError, VideoGenerationError) as exc:
            raise BackgroundNotFoundError(
                f"Background video not found at {self.background_path} and "
                "placeholder creation failed.\n"
                "Place your own vertical MP4 at:\n"
                f"  {self.background_path.resolve()}\n"
                f"Details: {exc}"
            ) from exc

        if not self.background_path.is_file() or self.background_path.stat().st_size == 0:
            raise BackgroundNotFoundError(
                f"Background video not found at {self.background_path}.\n"
                "Place a vertical MP4 file at that path and run again."
            )
        logger.info("Placeholder background created: %s", self.background_path.resolve())

    def _create_placeholder_background(self) -> None:
        self.background_path.parent.mkdir(parents=True, exist_ok=True)
        lavfi_source = (
            f"color=c=0x1a1a2e:s={self.width}x{self.height}:r={self.fps}:"
            f"d={PLACEHOLDER_DURATION_SECONDS}"
        )
        command = [
            self.ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            lavfi_source,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-t",
            str(PLACEHOLDER_DURATION_SECONDS),
            str(self.background_path.resolve()),
        ]
        logger.info("Creating placeholder background: %s", " ".join(command))
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise VideoGenerationError(
                f"Placeholder background creation failed: {stderr or result.returncode}"
            )

    def _verify_inputs(self) -> None:
        if not self.audio_path.is_file():
            raise AssetNotFoundError(
                f"Audio not found: {self.audio_path}. Run Phase 2 first."
            )
        if self.audio_path.stat().st_size == 0:
            raise AssetNotFoundError(f"Audio file is empty: {self.audio_path}")

        if not self.captions_path.is_file():
            raise AssetNotFoundError(
                f"Captions not found: {self.captions_path}. Run Phase 3 first."
            )
        if self.captions_path.stat().st_size == 0:
            raise AssetNotFoundError(f"Captions file is empty: {self.captions_path}")

        if not self.background_path.is_file():
            raise BackgroundNotFoundError(
                f"Background video not found: {self.background_path}"
            )

        logger.info("Audio: %s", self.audio_path.resolve())
        logger.info("Captions: %s", self.captions_path.resolve())
        logger.info("Background: %s", self.background_path.resolve())

    def _probe_duration(self, media_path: Path) -> float:
        command = [
            self.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path.resolve()),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except OSError as exc:
            raise VideoGenerationError(f"Failed to run ffprobe: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise VideoGenerationError(
                f"ffprobe failed for {media_path}: {stderr or result.returncode}"
            )

        try:
            return float((result.stdout or "").strip())
        except ValueError as exc:
            raise VideoGenerationError(
                f"Could not parse duration for {media_path}: {result.stdout!r}"
            ) from exc

    def _read_durations(self) -> None:
        self._audio_duration = self._probe_duration(self.audio_path)
        self._background_duration = self._probe_duration(self.background_path)
        logger.info("Narration duration: %.2f seconds", self._audio_duration)
        logger.info("Background duration: %.2f seconds", self._background_duration)
        print(
            f"  Narration: {self._audio_duration:.1f}s | "
            f"Background: {self._background_duration:.1f}s",
            flush=True,
        )

    def _log_background_preparation(self) -> None:
        if self._background_duration < self._audio_duration:
            logger.info(
                "Background (%.2fs) is shorter than narration (%.2fs); will loop",
                self._background_duration,
                self._audio_duration,
            )
            print(
                f"  Background will loop to match {self._audio_duration:.1f}s narration",
                flush=True,
            )
        else:
            logger.info("Background is long enough; trimming to narration with -shortest")
            print("  Background covers narration length", flush=True)

    def _build_video_filter(self) -> str:
        subtitles_path = escape_subtitles_path(self.captions_path)
        return (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
            f"crop={self.width}:{self.height},"
            f"fps={self.fps},"
            f"subtitles={subtitles_path}:force_style='{build_subtitle_force_style()}'"
        )

    def _render_video(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            self.output_path.unlink()

        video_filter = self._build_video_filter()
        timeout = max(
            120,
            int(self._audio_duration) + FFMPEG_RENDER_TIMEOUT_BUFFER,
        )

        command = [
            self.ffmpeg,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(self.background_path.resolve()),
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
            str(self.fps),
            "-shortest",
            str(self.output_path.resolve()),
        ]

        logger.info("Video filter: %s", video_filter)
        logger.info("Render timeout: %d seconds", timeout)
        logger.info("FFmpeg command: %s", " ".join(command))

        started_at = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started_at
            raise VideoGenerationError(
                f"FFmpeg render timed out after {elapsed:.1f}s (limit: {timeout}s)"
            ) from exc
        except OSError as exc:
            raise VideoGenerationError(f"Failed to run FFmpeg: {exc}") from exc

        elapsed = time.perf_counter() - started_at
        logger.info("FFmpeg render time: %.1f seconds", elapsed)
        print(f"  Render finished in {elapsed:.1f} seconds", flush=True)

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            raise VideoGenerationError(
                "FFmpeg render failed.\n"
                f"  return code: {result.returncode}\n"
                f"  stderr: {stderr or '(empty)'}\n"
                f"  stdout: {stdout or '(empty)'}"
            )

    def _verify_output(self) -> None:
        if not self.output_path.is_file():
            raise VideoGenerationError(
                f"Video file was not created: {self.output_path}"
            )
        size = self.output_path.stat().st_size
        if size == 0:
            raise VideoGenerationError(f"Video file is empty: {self.output_path}")

        output_duration = self._probe_duration(self.output_path)
        logger.info(
            "Output video: %d bytes, %.2f seconds",
            size,
            output_duration,
        )
        print(
            f"  Output: {size / (1024 * 1024):.1f} MB, {output_duration:.1f}s",
            flush=True,
        )

        if abs(output_duration - self._audio_duration) > 2.0:
            logger.warning(
                "Output duration (%.2fs) differs from narration (%.2fs)",
                output_duration,
                self._audio_duration,
            )
