"""Phase 2: Convert script text to narration audio using Piper TTS."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PIPER_EXECUTABLE = Path("C:/Tools/piper/piper.exe")
PIPER_EXECUTABLE = Path(os.environ.get("PIPER_EXECUTABLE", DEFAULT_PIPER_EXECUTABLE))
VOICE_MODEL = Path("models/piper/en_US-ryan-high.onnx")
VOICE_CONFIG = Path("models/piper/en_US-ryan-high.onnx.json")
SCRIPT_PATH = Path("scripts/script.txt")
OUTPUT_PATH = Path("audio/output.wav")
PROGRESS_STEPS = 5
PIPER_MIN_TIMEOUT_SECONDS = 60
PIPER_TIMEOUT_MULTIPLIER = 1.0
VOICE_SPEED = 1.25
WINDOWS_DLL_EXIT_CODE = 3221225781


class VoiceGeneratorError(Exception):
    """Base error for voice generation."""


class ScriptNotFoundError(VoiceGeneratorError):
    """Script file is missing or empty."""


class PiperNotFoundError(VoiceGeneratorError):
    """Piper executable is missing."""


class VoiceModelNotFoundError(VoiceGeneratorError):
    """Voice model or config is missing."""


class VoiceGenerationError(VoiceGeneratorError):
    """Piper failed to synthesize audio."""


def resolve_piper_executable(path: Path | str | None = None) -> Path:
    """Resolve Piper executable from argument, env var, or default path."""
    if path is not None:
        candidate = Path(path)
        if candidate.is_file():
            return candidate.resolve()

    env_path = os.environ.get("PIPER_EXECUTABLE")
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            return candidate.resolve()

    if DEFAULT_PIPER_EXECUTABLE.is_file():
        return DEFAULT_PIPER_EXECUTABLE.resolve()

    return DEFAULT_PIPER_EXECUTABLE


def calculate_piper_timeout(
    word_count: int,
    multiplier: float = PIPER_TIMEOUT_MULTIPLIER,
    minimum: int = PIPER_MIN_TIMEOUT_SECONDS,
) -> int:
    """Compute subprocess timeout from script length (seconds)."""
    return max(minimum, int(word_count * multiplier))


class VoiceGenerator:
    """Generate narration WAV from scripts/script.txt via Piper."""

    def __init__(
        self,
        piper_executable: Path | str | None = None,
        voice_model: Path | str = VOICE_MODEL,
        voice_config: Path | str = VOICE_CONFIG,
        script_path: Path | str = SCRIPT_PATH,
        output_path: Path | str = OUTPUT_PATH,
        voice_speed: float = VOICE_SPEED,
        timeout_multiplier: float = PIPER_TIMEOUT_MULTIPLIER,
    ) -> None:
        self.piper_executable = resolve_piper_executable(piper_executable)
        self.piper_dir = self.piper_executable.parent
        self.voice_model = Path(voice_model)
        self.voice_config = Path(voice_config)
        self.script_path = Path(script_path)
        self.output_path = Path(output_path)
        self.voice_speed = voice_speed
        self.timeout_multiplier = timeout_multiplier

    def generate(self) -> Path:
        """Read script, run Piper, and save audio/output.wav."""
        self._print_progress(1, "Verifying Piper executable...")
        self._verify_piper_executable()

        self._print_progress(2, "Verifying voice model...")
        self._verify_voice_model()

        self._print_progress(3, "Reading script...")
        script_text = self._read_script()

        self._print_progress(4, "Generating narration (Piper TTS)...")
        narration = self._prepare_narration_text(script_text)
        self._run_piper(narration)

        self._print_progress(5, "Verifying output audio...")
        self._verify_output()
        logger.info("Voice narration saved to %s", self.output_path.resolve())
        return self.output_path.resolve()

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _verify_piper_executable(self) -> None:
        if not self.piper_executable.is_file():
            raise PiperNotFoundError(
                f"Piper executable not found: {self.piper_executable}\n"
                "Install Piper to C:\\Tools\\piper\\piper.exe or set PIPER_EXECUTABLE."
            )
        logger.debug("Piper executable: %s", self.piper_executable)

    def _verify_voice_model(self) -> None:
        if not self.voice_model.is_file():
            raise VoiceModelNotFoundError(
                f"Voice model not found: {self.voice_model}"
            )
        if not self.voice_config.is_file():
            raise VoiceModelNotFoundError(
                f"Voice config not found: {self.voice_config}"
            )
        logger.debug("Voice model: %s", self.voice_model)

    def _read_script(self) -> str:
        if not self.script_path.is_file():
            raise ScriptNotFoundError(
                f"Script not found: {self.script_path}. Run Phase 1 first."
            )
        try:
            text = self.script_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ScriptNotFoundError(f"Cannot read script: {exc}") from exc
        if not text:
            raise ScriptNotFoundError(f"Script is empty: {self.script_path}")
        word_count = len(text.split())
        logger.info("Loaded script (%d words) from %s", word_count, self.script_path)
        return text

    @staticmethod
    def _prepare_narration_text(text: str) -> str:
        """Flatten formatted script lines into narration-friendly text."""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]
        if not paragraphs:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return " ".join(lines)
        return " ".join(re.sub(r"\s+", " ", paragraph) for paragraph in paragraphs)

    def _piper_env(self) -> dict[str, str]:
        """Ensure Piper's directory is on PATH so bundled DLLs load on Windows."""
        env = os.environ.copy()
        piper_dir = str(self.piper_dir)
        env["PATH"] = piper_dir + os.pathsep + env.get("PATH", "")
        return env

    def _run_piper(self, script_text: str) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        model_path = self.voice_model.resolve()
        config_path = self.voice_config.resolve()
        output_path = self.output_path.resolve()

        command = [
            str(self.piper_executable),
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--length_scale",
            str(self.voice_speed),
            "--output_file",
            str(output_path),
        ]

        logger.info("Piper executable: %s", self.piper_executable)
        logger.info("Voice model: %s", model_path)
        logger.info("Voice config: %s", config_path)
        logger.info("Voice speed (length_scale): %s", self.voice_speed)
        logger.info("Output WAV: %s", output_path)
        logger.info("Piper command: %s", " ".join(command))

        word_count = len(script_text.split())
        timeout = calculate_piper_timeout(word_count, self.timeout_multiplier)
        logger.info("Estimated timeout: %d seconds", timeout)
        print(f"  Estimated timeout: {timeout} seconds", flush=True)

        started_at = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                input=script_text,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
                cwd=str(self.piper_dir),
                env=self._piper_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started_at
            logger.error(
                "Piper timed out after %.1f seconds (limit: %d seconds)",
                elapsed,
                timeout,
            )
            raise VoiceGenerationError(
                f"Piper timed out after {timeout} seconds"
            ) from exc
        except OSError as exc:
            raise VoiceGenerationError(f"Failed to run Piper: {exc}") from exc

        elapsed = time.perf_counter() - started_at
        logger.info("Piper execution time: %.1f seconds", elapsed)
        print(f"  Piper finished in {elapsed:.1f} seconds", flush=True)

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        logger.info("Piper return code: %s", result.returncode)
        logger.info("Piper stdout: %s", stdout.strip())
        logger.info("Piper stderr: %s", stderr.strip())

        if result.returncode != 0:
            raise VoiceGenerationError(self._format_piper_failure(result.returncode, stdout, stderr))

    @staticmethod
    def _format_piper_failure(returncode: int, stdout: str, stderr: str) -> str:
        message = (
            f"Piper synthesis failed.\n"
            f"  return code: {returncode}\n"
            f"  stderr: {stderr.strip() or '(empty)'}\n"
            f"  stdout: {stdout.strip() or '(empty)'}"
        )
        if returncode == WINDOWS_DLL_EXIT_CODE:
            message += (
                "\n\nHint: Windows error 0xC0000135 — missing DLL. Ensure all Piper "
                f"files are in {DEFAULT_PIPER_EXECUTABLE.parent} and install the "
                "Microsoft Visual C++ 2015-2022 Redistributable (x64)."
            )
        return message

    def _verify_output(self) -> None:
        if not self.output_path.is_file():
            raise VoiceGenerationError(
                f"Piper did not create output file: {self.output_path}"
            )
        size = self.output_path.stat().st_size
        if size == 0:
            raise VoiceGenerationError(
                f"Output audio file is empty: {self.output_path}"
            )
        logger.info("Output audio size: %d bytes", size)
