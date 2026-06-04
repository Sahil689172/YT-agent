"""Phase 3: Generate subtitles from script (fast) or Whisper (fallback)."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from agents.subtitle_config import (
    log_subtitle_settings,
    segment_captions_from_script,
    segment_captions_for_shorts,
    subtitle_word_range_note,
    write_shorts_srt,
)

logger = logging.getLogger(__name__)

DEFAULT_FFMPEG = "ffmpeg"
WHISPER_MODEL_NAME = "base.en"
SCRIPT_PATH = Path("scripts/script.txt")
AUDIO_PATH = Path("audio/output.wav")
OUTPUT_SRT = Path("captions/output.srt")
PROGRESS_STEPS = 6


class CaptionGeneratorError(Exception):
    """Base error for caption generation."""


class AudioNotFoundError(CaptionGeneratorError):
    """Narration audio file is missing or empty."""


class FFmpegNotFoundError(CaptionGeneratorError):
    """FFmpeg executable is not available."""


class WhisperPackageNotFoundError(CaptionGeneratorError):
    """openai-whisper package is not installed."""


class WhisperModelLoadError(CaptionGeneratorError):
    """Failed to load the local Whisper model."""


class CaptionGenerationError(CaptionGeneratorError):
    """Transcription or SRT writing failed."""


def resolve_ffmpeg(ffmpeg: str | None = None) -> str:
    """Resolve FFmpeg executable from argument or PATH."""
    if ffmpeg:
        path = shutil.which(ffmpeg)
        if path:
            return path
        if Path(ffmpeg).is_file():
            return str(Path(ffmpeg).resolve())

    env_path = os.environ.get("FFMPEG_EXECUTABLE")
    if env_path and Path(env_path).is_file():
        return str(Path(env_path).resolve())

    path = shutil.which(DEFAULT_FFMPEG)
    if path:
        return path

    return DEFAULT_FFMPEG


def _import_whisper():
    """Import openai-whisper with a clear error if missing."""
    try:
        import whisper
        from whisper.utils import get_writer
    except ImportError as exc:
        raise WhisperPackageNotFoundError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        ) from exc
    return whisper, get_writer


def _force_whisper() -> bool:
    return os.environ.get("CAPTIONS_USE_WHISPER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class CaptionGenerator:
    """Generate SRT captions from script text (default) or Whisper (fallback)."""

    def __init__(
        self,
        ffmpeg: str | None = None,
        audio_path: Path | str = AUDIO_PATH,
        script_path: Path | str = SCRIPT_PATH,
        output_path: Path | str = OUTPUT_SRT,
        whisper_model: str = WHISPER_MODEL_NAME,
        language: str = "en",
    ) -> None:
        self.ffmpeg = resolve_ffmpeg(ffmpeg)
        self.audio_path = Path(audio_path)
        self.script_path = Path(script_path)
        self.output_path = Path(output_path)
        self.whisper_model_name = whisper_model
        self.language = language
        self._whisper_model = None

    def generate(self) -> Path:
        """Write captions/output.srt using script timing or Whisper."""
        self._print_progress(1, "Verifying narration audio...")
        self._verify_audio()

        if not _force_whisper() and self._try_script_captions():
            self._print_progress(6, "Verifying output.srt...")
            self._verify_output()
            logger.info("Captions saved to %s (script-based)", self.output_path.resolve())
            return self.output_path.resolve()

        logger.info("Using Whisper transcription (script unavailable or forced)")
        return self._generate_with_whisper()

    def _try_script_captions(self) -> bool:
        if not self.script_path.is_file():
            logger.info("No script at %s; Whisper required", self.script_path)
            return False

        script = self.script_path.read_text(encoding="utf-8").strip()
        if not script:
            logger.info("Script file empty; Whisper required")
            return False

        self._print_progress(2, "Building captions from script (skipping Whisper)...")
        duration = self._probe_audio_duration()
        log_subtitle_settings()
        cues = segment_captions_from_script(script, duration)
        if not cues:
            logger.warning("Script produced no cues; falling back to Whisper")
            return False

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            self.output_path.unlink()
        write_shorts_srt(cues, self.output_path)
        print(
            f"  Direct SRT from script: {len(cues)} blocks "
            f"({subtitle_word_range_note()}) — Whisper skipped",
            flush=True,
        )
        logger.info(
            "Script-based captions: %d cues, %.2fs audio",
            len(cues),
            duration,
        )
        return True

    def _probe_audio_duration(self) -> float:
        try:
            from agents.timeline_video_builder import probe_duration, resolve_ffmpeg_tool

            ffprobe = resolve_ffmpeg_tool("ffprobe", "FFPROBE_EXECUTABLE")
            return probe_duration(self.audio_path, ffprobe)
        except Exception as exc:
            logger.warning("ffprobe failed (%s); estimating from word count", exc)
            script = self.script_path.read_text(encoding="utf-8")
            return max(30.0, len(script.split()) * 0.35)

    def _generate_with_whisper(self) -> Path:
        self._print_progress(2, "Verifying FFmpeg...")
        self._verify_ffmpeg()

        self._print_progress(3, "Loading Whisper model...")
        model = self._load_whisper_model()

        self._print_progress(4, "Transcribing audio...")
        result = self._transcribe(model)

        self._print_progress(5, "Segmenting and writing Shorts-style captions...")
        self._write_srt_from_whisper(result)

        self._print_progress(6, "Verifying output.srt...")
        self._verify_output()

        logger.info("Captions saved to %s (Whisper)", self.output_path.resolve())
        return self.output_path.resolve()

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _verify_audio(self) -> None:
        if not self.audio_path.is_file():
            raise AudioNotFoundError(
                f"Audio not found: {self.audio_path}. Run Phase 2 first."
            )
        size = self.audio_path.stat().st_size
        if size == 0:
            raise AudioNotFoundError(f"Audio file is empty: {self.audio_path}")
        logger.info("Audio file: %s (%d bytes)", self.audio_path.resolve(), size)

    def _verify_ffmpeg(self) -> None:
        ffmpeg_path = shutil.which(self.ffmpeg)
        if ffmpeg_path is None and not Path(self.ffmpeg).is_file():
            raise FFmpegNotFoundError(
                "FFmpeg not found. Install FFmpeg and add it to PATH, "
                "or set FFMPEG_EXECUTABLE."
            )
        if ffmpeg_path:
            self.ffmpeg = ffmpeg_path
        try:
            result = subprocess.run(
                [self.ffmpeg, "-version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except OSError as exc:
            raise FFmpegNotFoundError(f"Cannot run FFmpeg: {exc}") from exc
        if result.returncode != 0:
            raise FFmpegNotFoundError("FFmpeg is installed but failed to run.")
        logger.info("FFmpeg executable: %s", self.ffmpeg)

    def _load_whisper_model(self):
        whisper, _get_writer = _import_whisper()
        logger.info("Loading Whisper model: %s", self.whisper_model_name)
        try:
            model = whisper.load_model(self.whisper_model_name)
        except Exception as exc:
            logger.error("Failed to load Whisper model: %s", exc)
            raise WhisperModelLoadError(
                f"Failed to load Whisper model '{self.whisper_model_name}': {exc}"
            ) from exc
        self._whisper_model = model
        logger.info("Whisper model loaded: %s", self.whisper_model_name)
        return model

    def _transcribe(self, model) -> dict:
        audio_path = str(self.audio_path.resolve())
        logger.info("Transcribing: %s", audio_path)
        try:
            result = model.transcribe(
                audio_path,
                language=self.language,
                verbose=False,
                word_timestamps=True,
            )
        except Exception as exc:
            logger.error("Whisper transcription failed: %s", exc)
            raise CaptionGenerationError(f"Whisper transcription failed: {exc}") from exc
        segment_count = len(result.get("segments") or [])
        logger.info("Transcription complete (%d segments)", segment_count)
        return result

    def _write_srt_from_whisper(self, result: dict) -> None:
        log_subtitle_settings()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            self.output_path.unlink()

        cues = segment_captions_for_shorts(result)
        if not cues:
            raise CaptionGenerationError(
                "No caption cues produced from transcription. "
                "Check audio quality and Whisper output."
            )

        write_shorts_srt(cues, self.output_path)
        logger.info("SRT file written: %s (%d cues)", self.output_path, len(cues))
        print(
            f"  Shorts captions: {len(cues)} blocks "
            f"({subtitle_word_range_note()})",
            flush=True,
        )

    def _verify_output(self) -> None:
        if not self.output_path.is_file():
            raise CaptionGenerationError(
                f"Subtitle file was not created: {self.output_path}"
            )
        content = self.output_path.read_text(encoding="utf-8").strip()
        if not content:
            raise CaptionGenerationError(f"Subtitle file is empty: {self.output_path}")
        if not self._looks_like_srt(content):
            raise CaptionGenerationError(
                f"Subtitle file does not appear to be valid SRT: {self.output_path}"
            )
        cue_count = len(re.findall(r"^\d+\s*$", content, re.MULTILINE))
        logger.info("SRT cues: %d, size: %d bytes", cue_count, self.output_path.stat().st_size)
        print(f"  Subtitle cues: {cue_count}", flush=True)

    @staticmethod
    def _looks_like_srt(content: str) -> bool:
        return "-->" in content and bool(re.search(r"^\d+\s*$", content, re.MULTILINE))
