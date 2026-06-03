"""Phase 4.5A: Convert script text into structured visual scenes via Ollama."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
DEFAULT_FFPROBE = "ffprobe"
SCRIPT_PATH = Path("scripts/script.txt")
AUDIO_PATH = Path("audio/output.wav")
SCENES_DIR = Path("scenes")
AGENTS_DIR = Path("agents")
OUTPUT_PATH = SCENES_DIR / "scenes.json"

SECONDS_PER_VISUAL = 5
ABSOLUTE_MIN_SCENES = 6
ABSOLUTE_MAX_SCENES = 15
MIN_SCENE_DURATION = 3
MAX_SCENE_DURATION = 8
DURATION_TOLERANCE_RATIO = 0.15
WORDS_PER_SECOND_ESTIMATE = 2.5
PROGRESS_STEPS = 5
MAX_GENERATION_ATTEMPTS = 3
SCENE_OBJECT_KEYS = ("scene_number", "duration_seconds", "title", "visual_description")

SYSTEM_PROMPT = """You are a visual director for YouTube Shorts.
Analyze the narration script and split it into logical visual scenes for AI image generation.

You MUST respond with one JSON object containing a "scenes" array.

Example (you must include at least 4 scenes):
{
  "scenes": [
    {
      "scene_number": 1,
      "duration_seconds": 8,
      "title": "Introduction",
      "visual_description": "Modern office workers discussing a marketing campaign"
    },
    {
      "scene_number": 2,
      "duration_seconds": 8,
      "title": "Data Analysis",
      "visual_description": "Marketing dashboard showing customer analytics and growth charts"
    }
  ]
}

Each scene object must have exactly these keys:
- scene_number (integer, starting at 1)
- duration_seconds (integer)
- title (short scene title, 2-6 words)
- visual_description (detailed image prompt for AI; 1-2 sentences)

Rules:
- Create one visual segment approximately every 5 seconds of narration
- The "scenes" array length must be within the requested range
- Each segment should be about 4-6 seconds (duration_seconds)
- Sum of duration_seconds must be close to the target total duration provided
- No markdown, no code fences, no text outside the JSON object"""

USER_PROMPT_TEMPLATE = """Script:
{script}

Target total narration duration: {target_duration:.0f} seconds
Target visual count: {target_visuals} (one visual every ~{seconds_per_visual} seconds)
Create exactly {min_scenes} to {max_scenes} visual segments (required minimum: {min_scenes}).
Each segment covers a distinct moment in the script.
The sum of all duration_seconds must be approximately {target_duration:.0f} seconds.

Return JSON: {{"scenes": [ ... at least {min_scenes} scene objects ... ]}}"""

RETRY_USER_SUFFIX = """

IMPORTANT: Your previous response was invalid or had too few scenes.
Return JSON with key "scenes" containing an array of at least {min_scenes} scene objects.
Do not return a single scene — return the full array."""


class SceneAgentError(Exception):
    """Base error for scene generation."""


class ScriptNotFoundError(SceneAgentError):
    """Script file is missing or empty."""


class SceneOllamaConnectionError(SceneAgentError):
    """Ollama is unreachable or not running."""


class SceneOllamaModelError(SceneAgentError):
    """Requested Ollama model is missing or failed."""


class SceneValidationError(SceneAgentError):
    """Generated scenes failed validation."""


class SceneGenerationError(SceneAgentError):
    """Scene generation or save failed."""


def resolve_ffprobe() -> str:
    """Resolve ffprobe from PATH or environment."""
    env_path = os.environ.get("FFPROBE_EXECUTABLE")
    if env_path and Path(env_path).is_file():
        return str(Path(env_path).resolve())
    path = shutil.which(DEFAULT_FFPROBE)
    return path if path else DEFAULT_FFPROBE


def probe_audio_duration(audio_path: Path) -> float | None:
    """Return narration duration in seconds, or None if probing fails."""
    if not audio_path.is_file() or audio_path.stat().st_size == 0:
        return None

    ffprobe = resolve_ffprobe()
    if shutil.which(ffprobe) is None and not Path(ffprobe).is_file():
        return None

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path.resolve()),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return None


def estimate_duration_from_script(script: str) -> float:
    """Estimate narration length from word count when audio is unavailable."""
    word_count = len(script.split())
    return max(30.0, min(45.0, word_count / WORDS_PER_SECOND_ESTIMATE))


def calculate_visual_segment_counts(duration_seconds: float) -> tuple[int, int, int]:
    """Return (target_visuals, min_scenes, max_scenes) — ~1 visual every 5 seconds."""
    target = max(ABSOLUTE_MIN_SCENES, round(duration_seconds / SECONDS_PER_VISUAL))
    min_scenes = max(ABSOLUTE_MIN_SCENES, target - 1)
    max_scenes = min(ABSOLUTE_MAX_SCENES, target + 1)
    return target, min_scenes, max_scenes


def _repair_json(text: str) -> str:
    """Fix common JSON issues from LLM output."""
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text


def _extract_json_blob(raw: str) -> str:
    """Strip markdown fences and surrounding prose from model output."""
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _coerce_to_scene_list(data: Any) -> list[dict[str, Any]]:
    """Normalize parsed JSON into a list of scene dicts."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        for key in ("scenes", "scene_list", "data", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        # Single scene object — too few; let enforce_scene_count reject it
        if all(key in data for key in SCENE_OBJECT_KEYS):
            return [data]

    return []


def enforce_scene_count(
    scenes: list[dict[str, Any]],
    min_scenes: int = ABSOLUTE_MIN_SCENES,
    max_scenes: int = ABSOLUTE_MAX_SCENES,
) -> list[dict[str, Any]]:
    """Require a valid scene count before accepting model output."""
    count = len(scenes)
    if count < min_scenes:
        raise SceneValidationError(
            f"Expected {min_scenes}-{max_scenes} scenes; got {count}."
        )
    if count > max_scenes:
        logger.warning("Trimming %d scenes to maximum %d", count, max_scenes)
        return scenes[:max_scenes]
    return scenes


def _extract_scene_objects_regex(text: str) -> list[dict[str, Any]]:
    """Find individual scene JSON objects when the model omits the outer array."""
    scenes: list[dict[str, Any]] = []
    pattern = re.compile(
        r"\{[^{}]*\"scene_number\"\s*:\s*\d+[^{}]*\}",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        chunk = _repair_json(match.group())
        try:
            item = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and "visual_description" in item:
            scenes.append(item)
    return scenes


def parse_scenes_json(raw: str) -> list[dict[str, Any]]:
    """Extract and parse a JSON array from model output (multiple strategies)."""
    text = _extract_json_blob(raw)
    errors: list[str] = []

    # Strategy 1: bracket-delimited array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        candidate = _repair_json(text[start : end + 1])
        try:
            data = json.loads(candidate)
            scenes = _coerce_to_scene_list(data)
            if scenes:
                return enforce_scene_count(scenes)
        except json.JSONDecodeError as exc:
            errors.append(f"array parse: {exc}")
        except SceneValidationError as exc:
            errors.append(str(exc))

    # Strategy 2: parse entire blob (object wrapper or lone array)
    try:
        data = json.loads(_repair_json(text))
        scenes = _coerce_to_scene_list(data)
        if scenes:
            return enforce_scene_count(scenes)
    except json.JSONDecodeError as exc:
        errors.append(f"full parse: {exc}")
    except SceneValidationError as exc:
        errors.append(str(exc))

    # Strategy 3: extract individual scene objects
    scenes = _extract_scene_objects_regex(text)
    if scenes:
        try:
            return enforce_scene_count(scenes)
        except SceneValidationError as exc:
            errors.append(str(exc))
    if scenes:
        errors.append(f"regex found only {len(scenes)} scene(s)")

    logger.debug("Failed to parse scene JSON. Response preview: %s", text[:500])
    detail = "; ".join(errors) if errors else "no JSON structure found"
    raise SceneValidationError(f"Could not parse scenes from model response ({detail}).")


def normalize_scene_durations(
    scenes: list[dict[str, Any]],
    target_duration: float,
) -> list[dict[str, Any]]:
    """Scale scene durations so their sum matches the target narration length."""
    total = sum(int(s["duration_seconds"]) for s in scenes)
    if total <= 0:
        raise SceneValidationError("Scene durations must be positive.")

    if abs(total - target_duration) / target_duration <= DURATION_TOLERANCE_RATIO:
        return scenes

    target_int = int(round(target_duration))
    durations = [
        max(MIN_SCENE_DURATION, int(round(scene["duration_seconds"] * target_int / total)))
        for scene in scenes
    ]
    drift = target_int - sum(durations)
    durations[-1] = max(MIN_SCENE_DURATION, durations[-1] + drift)

    scaled: list[dict[str, Any]] = []
    for scene, duration in zip(scenes, durations, strict=True):
        updated = dict(scene)
        updated["duration_seconds"] = duration
        scaled.append(updated)

    return scaled


class SceneAgent:
    """Generate structured visual scenes from scripts/script.txt."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        script_path: Path | str = SCRIPT_PATH,
        audio_path: Path | str = AUDIO_PATH,
        output_path: Path | str = OUTPUT_PATH,
    ) -> None:
        self.model = model
        self.script_path = Path(script_path)
        self.audio_path = Path(audio_path)
        self.output_path = Path(output_path)
        self.min_scenes = ABSOLUTE_MIN_SCENES
        self.max_scenes = ABSOLUTE_MAX_SCENES
        self.target_visual_count = ABSOLUTE_MIN_SCENES
        self._script_text = ""
        self._target_duration = 0.0

    def generate(self) -> tuple[list[dict[str, Any]], Path]:
        """Read script, generate scenes, validate, and save scenes/scenes.json."""
        self._ensure_dirs()
        self._print_progress(1, "Reading script...")
        self._read_script()

        self._print_progress(2, "Analyzing content...")
        self._analyze_duration()

        self._print_progress(3, "Generating scenes...")
        scenes = self._generate_scenes()

        self._print_progress(4, "Validating JSON...")
        scenes = self._validate_and_normalize(scenes)

        self._print_progress(5, "Saving scenes...")
        path = self._save(scenes)
        self._print_scene_summary(scenes)
        return scenes, path

    def _print_progress(self, step: int, message: str) -> None:
        print(f"[{step}/{PROGRESS_STEPS}] {message}", flush=True)
        logger.info("%s", message)

    def _ensure_dirs(self) -> None:
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        SCENES_DIR.mkdir(parents=True, exist_ok=True)

    def _read_script(self) -> None:
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
        self._script_text = text
        word_count = len(text.split())
        logger.info(
            "Loaded script (%d words) from %s",
            word_count,
            self.script_path.resolve(),
        )

    def _analyze_duration(self) -> None:
        probed = probe_audio_duration(self.audio_path)
        if probed is not None:
            self._target_duration = probed
            source = f"audio ({self.audio_path})"
        else:
            self._target_duration = estimate_duration_from_script(self._script_text)
            source = "script word-count estimate"
        target, min_scenes, max_scenes = calculate_visual_segment_counts(
            self._target_duration
        )
        self.target_visual_count = target
        self.min_scenes = min_scenes
        self.max_scenes = max_scenes
        logger.info(
            "Target narration duration: %.1f seconds (%s)",
            self._target_duration,
            source,
        )
        logger.info(
            "Target visuals: %d (range %d-%d, ~1 every %ds)",
            target,
            min_scenes,
            max_scenes,
            SECONDS_PER_VISUAL,
        )
        print(f"  Target duration: {self._target_duration:.1f}s ({source})", flush=True)
        print(
            f"  Target visuals: {target} (scenes {min_scenes}-{max_scenes}, "
            f"~1 every {SECONDS_PER_VISUAL}s)",
            flush=True,
        )

    def _generate_scenes(self) -> list[dict[str, Any]]:
        prompt = USER_PROMPT_TEMPLATE.format(
            script=self._script_text,
            target_duration=self._target_duration,
            target_visuals=self.target_visual_count,
            seconds_per_visual=SECONDS_PER_VISUAL,
            min_scenes=self.min_scenes,
            max_scenes=self.max_scenes,
        )
        last_error: SceneValidationError | None = None

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            user_prompt = prompt
            if attempt > 1:
                logger.info(
                    "Regenerating scenes (attempt %d/%d)",
                    attempt,
                    MAX_GENERATION_ATTEMPTS,
                )
                user_prompt += RETRY_USER_SUFFIX.format(min_scenes=self.min_scenes)

            raw = self._chat(SYSTEM_PROMPT, user_prompt, json_mode=True)
            try:
                parsed = parse_scenes_json(raw)
                scenes = self._validate_and_normalize(parsed)
                if attempt > 1:
                    logger.info(
                        "Scenes generated successfully on attempt %d (%d scenes)",
                        attempt,
                        len(scenes),
                    )
                return scenes
            except SceneValidationError as exc:
                last_error = exc
                logger.warning("Scene generation failed (attempt %d): %s", attempt, exc)

        assert last_error is not None
        raise last_error

    def _validate_and_normalize(
        self,
        raw_scenes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enforce_scene_count(raw_scenes, self.min_scenes, self.max_scenes)

        scenes: list[dict[str, Any]] = []
        for index, item in enumerate(raw_scenes, start=1):
            if not isinstance(item, dict):
                raise SceneValidationError(f"Scene {index} must be a JSON object.")

            required = ("scene_number", "duration_seconds", "title", "visual_description")
            missing = [key for key in required if key not in item]
            if missing:
                raise SceneValidationError(f"Scene {index} missing keys: {', '.join(missing)}")

            try:
                scene_number = int(item["scene_number"])
                duration_seconds = int(item["duration_seconds"])
            except (TypeError, ValueError) as exc:
                raise SceneValidationError(
                    f"Scene {index} has invalid scene_number or duration_seconds."
                ) from exc

            title = str(item["title"]).strip()
            visual_description = str(item["visual_description"]).strip()

            if scene_number != index:
                scene_number = index
            if duration_seconds < MIN_SCENE_DURATION or duration_seconds > MAX_SCENE_DURATION:
                raise SceneValidationError(
                    f"Scene {index} duration {duration_seconds}s out of range "
                    f"({MIN_SCENE_DURATION}-{MAX_SCENE_DURATION})."
                )
            if not title:
                raise SceneValidationError(f"Scene {index} title is empty.")
            if len(visual_description) < 10:
                raise SceneValidationError(
                    f"Scene {index} visual_description is too short."
                )

            scenes.append(
                {
                    "scene_number": scene_number,
                    "duration_seconds": duration_seconds,
                    "title": title,
                    "visual_description": visual_description,
                }
            )

        scenes = normalize_scene_durations(scenes, self._target_duration)
        total = sum(s["duration_seconds"] for s in scenes)
        logger.info(
            "Validated %d scenes, total duration %ds (target %.1fs)",
            len(scenes),
            total,
            self._target_duration,
        )
        return scenes

    def _save(self, scenes: list[dict[str, Any]]) -> Path:
        self._ensure_dirs()
        try:
            body = json.dumps(scenes, indent=2, ensure_ascii=False) + "\n"
            self.output_path.write_text(body, encoding="utf-8")
        except OSError as exc:
            raise SceneGenerationError(f"Failed to save scenes: {exc}") from exc
        logger.info("Scenes saved to %s", self.output_path.resolve())
        return self.output_path.resolve()

    def _print_scene_summary(self, scenes: list[dict[str, Any]]) -> None:
        print("\nScene summary:", flush=True)
        for scene in scenes:
            print(
                f"  Scene {scene['scene_number']} - {scene['title']} "
                f"({scene['duration_seconds']}s)",
                flush=True,
            )

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        chat_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            chat_kwargs["format"] = "json"

        try:
            response = ollama.chat(**chat_kwargs)
        except ConnectionError as exc:
            raise SceneOllamaConnectionError(
                "Cannot connect to Ollama. Is it running? (ollama serve)"
            ) from exc
        except Exception as exc:
            err = str(exc).lower()
            if "connection" in err or "refused" in err or "connect" in err:
                raise SceneOllamaConnectionError(
                    "Cannot connect to Ollama. Is it running? (ollama serve)"
                ) from exc
            if "not found" in err or "model" in err:
                raise SceneOllamaModelError(
                    f"Model '{self.model}' not available. Run: ollama pull {self.model}"
                ) from exc
            raise SceneGenerationError(f"Ollama request failed: {exc}") from exc

        message = response.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise SceneGenerationError("Ollama returned an empty response.")
        return content
