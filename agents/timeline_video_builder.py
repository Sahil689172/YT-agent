"""Phase 4.5C (legacy): Build final Short from scene images with motion, narration, and subtitles."""

from __future__ import annotations

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

logger = logging.getLogger(__name__)

DEFAULT_FFMPEG = "ffmpeg"
DEFAULT_FFPROBE = "ffprobe"
SCENES_DIR = Path("assets/scenes")
SCENES_JSON_PATH = Path("scenes/scenes.json")
AUDIO_PATH = Path("audio/output.wav")
CAPTIONS_PATH = Path("captions/output.srt")
OUTPUT_PATH = Path("videos/output.mp4")
VIDEOS_DIR = Path("videos")

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
MIN_SEGMENT_SECONDS = 2.0
PROGRESS_STEPS = 8
FFMPEG_TIMEOUT_BUFFER = 180

MOTION_EFFECTS = (
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "ken_burns",
)

SUBTITLE_FORCE_STYLE = (
    "FontName=Arial,"
    "FontSize=20,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BorderStyle=1,"
    "Outline=2,"
    "Shadow=0,"
    "Alignment=2,"
    "MarginV=45,"
    "WrapStyle=0"
)


class TimelineVideoBuilderError(Exception):
    """Base error for timeline video building."""


class ImagesNotFoundError(TimelineVideoBuilderError):
    """No scene images found."""


class NarrationNotFoundError(TimelineVideoBuilderError):
    """Narration audio is missing."""


class CaptionsNotFoundError(TimelineVideoBuilderError):
    """Captions file is missing."""


class FFmpegNotFoundError(TimelineVideoBuilderError):
    """FFmpeg or ffprobe is not available."""


class TimelineRenderError(TimelineVideoBuilderError):
    """FFmpeg failed during timeline rendering."""


@dataclass(frozen=True)
class TimelineEntry:
    scene_number: int
    image_path: Path
    duration_seconds: float
    motion_effect: str


@dataclass
class TimelineBuildResult:
    output_path: Path
    image_count: int
    narration_seconds: float
    final_seconds: float


def resolve_ffmpeg_tool(name: str, env_var: str | None = None) -> str:
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path and Path(env_path).is_file():
            return str(Path(env_path).resolve())
    path = shutil.which(name)
    return path if path else name


def escape_subtitles_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(Path.cwd())
        escaped = relative.as_posix()
    except ValueError:
        escaped = path.resolve().as_posix()
        if len(escaped) >= 2 and escaped[1] == ":":
            escaped = escaped[0] + "\\:" + escaped[2:]
    return escaped.replace("'", r"\'").replace("\\", "/")


def probe_duration(media_path: Path, ffprobe: str) -> float:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path.resolve()),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise TimelineRenderError(
            f"ffprobe failed for {media_path}: {(result.stderr or '').strip()}"
        )
    try:
        return float((result.stdout or "").strip())
    except ValueError as exc:
        raise TimelineRenderError(f"Invalid duration for {media_path}") from exc


def list_scene_images(scenes_dir: Path) -> list[Path]:
    """Return scene images sorted by scene number."""
    pattern = re.compile(r"scene_(\d+)\.(jpg|jpeg|png|webp)$", re.I)
    images: list[tuple[int, Path]] = []
    for path in scenes_dir.iterdir():
        if not path.is_file():
            continue
        match = pattern.match(path.name)
        if match:
            images.append((int(match.group(1)), path))
    images.sort(key=lambda item: item[0])
    return [path for _, path in images]


def build_motion_filter(effect: str, frames: int) -> str:
    """Build FFmpeg zoompan motion filter for a still image segment."""
    w, h, fps = VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
    size = f"{w}x{h}"
    d = max(frames, 1)

    if effect == "zoom_in":
        z_expr = "min(1.0+0.0007*on,1.22)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif effect == "zoom_out":
        z_expr = "max(1.22-0.0007*on,1.0)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif effect == "pan_left":
        z_expr = "1.15"
        x_expr = f"(iw-ow)/2*(1-on/{d})"
        y_expr = "ih/2-(ih/zoom/2)"
    elif effect == "pan_right":
        z_expr = "1.15"
        x_expr = f"(iw-ow)/2*(on/{d})"
        y_expr = "ih/2-(ih/zoom/2)"
    else:  # ken_burns
        z_expr = "min(1.0+0.0005*on,1.18)"
        x_expr = f"(iw-ow)/2*(on/{d})"
        y_expr = "ih/2-(ih/zoom/2)"

    return (
        f"scale={w * 4}:{h * 4}:force_original_aspect_ratio=increase,"
        f"crop={w * 4}:{h * 4},"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={d}:s={size}:fps={fps}"
    )


class TimelineVideoBuilder:
    """Assemble one motion Short from scene images, narration, and captions."""

    def __init__(
        self,
        ffmpeg: str | None = None,
        ffprobe: str | None = None,
        scenes_dir: Path | str = SCENES_DIR,
        audio_path: Path | str = AUDIO_PATH,
        captions_path: Path | str = CAPTIONS_PATH,
        output_path: Path | str = OUTPUT_PATH,
        width: int = VIDEO_WIDTH,
        height: int = VIDEO_HEIGHT,
        fps: int = VIDEO_FPS,
    ) -> None:
        self.ffmpeg = resolve_ffmpeg_tool(ffmpeg or DEFAULT_FFMPEG, "FFMPEG_EXECUTABLE")
        self.ffprobe = resolve_ffmpeg_tool(ffprobe or DEFAULT_FFPROBE, "FFPROBE_EXECUTABLE")
        self.scenes_dir = Path(scenes_dir)
        self.audio_path = Path(audio_path)
        self.captions_path = Path(captions_path)
        self.output_path = Path(output_path)
        self.width = width
        self.height = height
        self.fps = fps
        self._images: list[Path] = []
        self._narration_seconds = 0.0
        self._timeline: list[TimelineEntry] = []
        self._temp_dir: Path | None = None

    def generate(self) -> TimelineBuildResult:
        """Render videos/output.mp4 from scene images with motion and narration."""
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        self._verify_ffmpeg()

        self._print_progress(1, "Reading images...")
        self._images = self._read_images()

        self._print_progress(2, "Reading narration...")
        self._narration_seconds = self._read_narration_duration()

        self._print_progress(3, "Building timeline...")
        self._timeline = self._build_timeline()

        self._temp_dir = Path(tempfile.mkdtemp(prefix="yt_timeline_"))
        try:
            self._print_progress(4, "Applying motion effects...")
            segment_paths = self._render_motion_segments()

            self._print_progress(5, "Rendering visual video...")
            visual_path = self._concat_segments(segment_paths)

            self._print_progress(6, "Adding narration...")
            self._print_progress(7, "Adding subtitles...")
            self._finalize_with_audio_and_subtitles(visual_path)

            self._print_progress(8, "Completed")
            self._verify_output()
            final_seconds = probe_duration(self.output_path, self.ffprobe)
            result = TimelineBuildResult(
                output_path=self.output_path.resolve(),
                image_count=len(self._images),
                narration_seconds=self._narration_seconds,
                final_seconds=final_seconds,
            )
            self._print_summary(result)
            return result
        finally:
            if self._temp_dir and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.debug("Removed temp timeline directory")

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _verify_ffmpeg(self) -> None:
        for tool in (self.ffmpeg, self.ffprobe):
            if shutil.which(tool) is None and not Path(tool).is_file():
                raise FFmpegNotFoundError(f"{tool} not found on PATH.")
        logger.info("FFmpeg: %s", self.ffmpeg)
        logger.info("FFprobe: %s", self.ffprobe)

    def _read_images(self) -> list[Path]:
        if not self.scenes_dir.is_dir():
            raise ImagesNotFoundError(f"Scenes directory not found: {self.scenes_dir}")
        images = list_scene_images(self.scenes_dir)
        if not images:
            raise ImagesNotFoundError(
                f"No scene images in {self.scenes_dir}. Run Phase 4.5B first."
            )
        logger.info("Found %d scene images", len(images))
        for path in images:
            logger.info("  %s", path.name)
        return images

    def _read_narration_duration(self) -> float:
        if not self.audio_path.is_file():
            raise NarrationNotFoundError(
                f"Narration not found: {self.audio_path}. Run Phase 2 first."
            )
        duration = probe_duration(self.audio_path, self.ffprobe)
        logger.info("Narration duration: %.2f seconds", duration)
        print(f"  Narration length: {duration:.1f}s", flush=True)
        return duration

    def _load_scene_durations(self) -> dict[int, float]:
        """Load per-scene durations from scenes.json when available."""
        if not SCENES_JSON_PATH.is_file():
            return {}
        try:
            data = json.loads(SCENES_JSON_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if isinstance(data, dict) and "scenes" in data:
            data = data["scenes"]
        if not isinstance(data, list):
            return {}
        durations: dict[int, float] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                number = int(item["scene_number"])
                durations[number] = max(
                    MIN_SEGMENT_SECONDS,
                    float(item.get("duration_seconds") or MIN_SEGMENT_SECONDS),
                )
            except (KeyError, TypeError, ValueError):
                continue
        return durations

    def _build_timeline(self) -> list[TimelineEntry]:
        count = len(self._images)
        scene_durations = self._load_scene_durations()
        use_scene_durations = bool(scene_durations)

        raw: list[tuple[int, Path, float, str]] = []
        for image_path in self._images:
            match = re.search(r"scene_(\d+)", image_path.name, re.I)
            scene_number = int(match.group(1)) if match else len(raw) + 1
            if use_scene_durations and scene_number in scene_durations:
                duration = scene_durations[scene_number]
            else:
                duration = self._narration_seconds / count
            raw.append((scene_number, image_path, duration, random.choice(MOTION_EFFECTS)))

        if use_scene_durations:
            total = sum(item[2] for item in raw)
            if total > 0 and abs(total - self._narration_seconds) > 0.05:
                ratio = self._narration_seconds / total
                normalized: list[tuple[int, Path, float, str]] = []
                for scene_number, image_path, duration, effect in raw:
                    normalized.append(
                        (
                            scene_number,
                            image_path,
                            max(MIN_SEGMENT_SECONDS, duration * ratio),
                            effect,
                        )
                    )
                drift = self._narration_seconds - sum(item[2] for item in normalized)
                if normalized and abs(drift) > 0.05:
                    last = normalized[-1]
                    normalized[-1] = (
                        last[0],
                        last[1],
                        max(MIN_SEGMENT_SECONDS, last[2] + drift),
                        last[3],
                    )
                raw = normalized
            per_note = "scenes.json durations (normalized)"
        else:
            per_note = f"equal split ({self._narration_seconds / count:.1f}s each)"

        timeline: list[TimelineEntry] = []
        for scene_number, image_path, duration, effect in raw:
            timeline.append(
                TimelineEntry(
                    scene_number=scene_number,
                    image_path=image_path,
                    duration_seconds=duration,
                    motion_effect=effect,
                )
            )
            logger.info(
                "Timeline scene %d: %.2fs, motion=%s, file=%s",
                scene_number,
                duration,
                effect,
                image_path.name,
            )

        print(
            f"  {count} images, {per_note} ≈ {self._narration_seconds:.1f}s total",
            flush=True,
        )
        return timeline

    def _render_motion_segments(self) -> list[Path]:
        assert self._temp_dir is not None
        segment_paths: list[Path] = []

        for entry in self._timeline:
            frames = max(1, int(round(entry.duration_seconds * self.fps)))
            filter_chain = build_motion_filter(entry.motion_effect, frames)
            segment_path = self._temp_dir / f"seg_{entry.scene_number:03d}.mp4"

            command = [
                self.ffmpeg,
                "-y",
                "-loop",
                "1",
                "-framerate",
                str(self.fps),
                "-i",
                str(entry.image_path.resolve()),
                "-vf",
                filter_chain,
                "-t",
                str(entry.duration_seconds),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(segment_path),
            ]
            logger.info(
                "Rendering scene %d (%s, %.2fs): %s",
                entry.scene_number,
                entry.motion_effect,
                entry.duration_seconds,
                entry.image_path.name,
            )
            self._run_ffmpeg(command, f"motion segment {entry.scene_number}")
            segment_paths.append(segment_path)

        return segment_paths

    def _concat_segments(self, segment_paths: list[Path]) -> Path:
        assert self._temp_dir is not None
        concat_list = self._temp_dir / "concat.txt"
        lines = [f"file '{path.resolve().as_posix()}'" for path in segment_paths]
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

        visual_path = self._temp_dir / "visual_concat.mp4"
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
            str(self.fps),
            str(visual_path),
        ]
        self._run_ffmpeg(command, "concat visual timeline")
        logger.info("Visual timeline concatenated: %s", visual_path)
        return visual_path

    def _finalize_with_audio_and_subtitles(self, visual_path: Path) -> None:
        if not self.captions_path.is_file():
            raise CaptionsNotFoundError(
                f"Captions not found: {self.captions_path}. Run Phase 3 first."
            )

        if self.output_path.exists():
            self.output_path.unlink()

        subtitles = escape_subtitles_path(self.captions_path)
        video_filter = f"subtitles={subtitles}:force_style='{SUBTITLE_FORCE_STYLE}'"

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
            str(self.fps),
            "-shortest",
            str(self.output_path.resolve()),
        ]
        logger.info("Final encode with narration and subtitles")
        self._run_ffmpeg(command, "final video with audio and subtitles")

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
        logger.info("FFmpeg %s completed in %.1fs (code %s)", label, elapsed, result.returncode)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            raise TimelineRenderError(
                f"FFmpeg failed during {label}.\n"
                f"  return code: {result.returncode}\n"
                f"  stderr: {stderr or '(empty)'}\n"
                f"  stdout: {stdout or '(empty)'}"
            )

    def _verify_output(self) -> None:
        if not self.output_path.is_file():
            raise TimelineRenderError(f"Output video was not created: {self.output_path}")
        size = self.output_path.stat().st_size
        if size == 0:
            raise TimelineRenderError(f"Output video is empty: {self.output_path}")
        logger.info("Output video: %d bytes", size)

    def _print_summary(self, result: TimelineBuildResult) -> None:
        print("\nTimeline video summary:", flush=True)
        print(f"  Images Used: {result.image_count}", flush=True)
        print(f"  Narration Length: {result.narration_seconds:.1f} seconds", flush=True)
        print(f"  Final Duration: {result.final_seconds:.1f} seconds", flush=True)
        print(f"  Output: {result.output_path}", flush=True)
