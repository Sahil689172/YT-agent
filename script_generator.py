"""YouTube Shorts script generation via local Ollama."""

from __future__ import annotations

import logging
import re
import textwrap
from pathlib import Path

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
TARGET_MIN_WORDS = 140
TARGET_MAX_WORDS = 180
MIN_WORDS = 120
MAX_WORDS = 200
MAX_REGENERATIONS = 3
MAX_GENERATION_ATTEMPTS = 1 + MAX_REGENERATIONS
DEFAULT_OUTPUT = Path("scripts/output.txt")
DEFAULT_FORMATTED = Path("scripts/script.txt")
WRAP_WIDTH = 90

SYSTEM_PROMPT = f"""You write spoken-word scripts for YouTube Shorts.
Output ONLY the script text the speaker says aloud.
Rules:
- {TARGET_MIN_WORDS} to {TARGET_MAX_WORDS} words total (about 50-60 seconds when spoken aloud)
- No narrator labels (e.g. Narrator:, Voiceover:)
- No scene directions or stage directions in brackets or parentheses
- No host references (e.g. "I'm your host", "welcome back to the channel")
- No titles, headings, bullet points, or metadata
- Conversational, punchy, hook in the first line, strong close"""

USER_PROMPT_TEMPLATE = f"""Write a YouTube Shorts script about: {{topic}}

Remember: plain spoken script only, {TARGET_MIN_WORDS}-{TARGET_MAX_WORDS} words (50-60 seconds of narration)."""


class ScriptGeneratorError(Exception):
    """Base error for script generation."""


class OllamaConnectionError(ScriptGeneratorError):
    """Ollama is unreachable or not running."""


class OllamaModelError(ScriptGeneratorError):
    """Requested model is missing or failed."""


class ScriptValidationError(ScriptGeneratorError):
    """Generated script failed length or format checks."""


def clean_script_text(text: str, wrap_width: int = WRAP_WIDTH) -> str:
    """Format script for readability without changing words or order."""
    text = text.strip()
    if not text:
        return ""

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
    if not blocks:
        blocks = [text]

    paragraphs: list[str] = []
    for block in blocks:
        normalized = re.sub(r"[^\S\n]+", " ", block).strip()
        sentences = _split_sentences(normalized)
        if not sentences:
            continue
        if len(sentences) == 1:
            paragraphs.append(sentences[0])
        else:
            paragraphs.extend(_group_sentences(sentences))

    wrapped = [
        textwrap.fill(
            paragraph,
            width=wrap_width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        for paragraph in paragraphs
    ]
    return "\n\n".join(wrapped) + "\n"


def _split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries while preserving each sentence verbatim."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _group_sentences(sentences: list[str]) -> list[str]:
    """Merge sentences into readable paragraphs without altering wording."""
    if len(sentences) <= 1:
        return sentences
    if len(sentences) <= 4:
        mid = (len(sentences) + 1) // 2
        return [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
    return [" ".join(sentences[i : i + 2]) for i in range(0, len(sentences), 2)]


class ScriptGenerator:
    """Generate and persist YouTube Shorts scripts using Ollama."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        output_path: Path | str = DEFAULT_OUTPUT,
        formatted_path: Path | str = DEFAULT_FORMATTED,
        min_words: int = MIN_WORDS,
        max_words: int = MAX_WORDS,
    ) -> None:
        self.model = model
        self.output_path = Path(output_path)
        self.formatted_path = Path(formatted_path)
        self.min_words = min_words
        self.max_words = max_words

    def generate(self, topic: str) -> str:
        """Generate a script for the given topic with automatic length retries."""
        topic = topic.strip()
        if not topic:
            raise ScriptGeneratorError("Topic cannot be empty.")

        last_script: str | None = None
        last_count = 0

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            if attempt > 1:
                logger.info(
                    "Regenerating script (attempt %d/%d); previous length was %d words",
                    attempt,
                    MAX_GENERATION_ATTEMPTS,
                    last_count,
                )

            script = self._request_script(topic)
            last_script = script
            last_count = self._word_count(script)
            self._validate_forbidden_content(script)

            if self.min_words <= last_count <= self.max_words:
                if attempt > 1:
                    logger.info(
                        "Script accepted on attempt %d (%d words)",
                        attempt,
                        last_count,
                    )
                return script

            if attempt < MAX_GENERATION_ATTEMPTS:
                logger.warning(
                    "Script length %d words (expected %d-%d); regenerating (%d/%d retries left)",
                    last_count,
                    self.min_words,
                    self.max_words,
                    MAX_GENERATION_ATTEMPTS - attempt,
                    MAX_REGENERATIONS,
                )
                continue

        assert last_script is not None
        raise ScriptValidationError(
            f"Script length is {last_count} words after {MAX_GENERATION_ATTEMPTS} attempts; "
            f"expected {self.min_words}-{self.max_words}."
        )

    def _request_script(self, topic: str) -> str:
        """Call Ollama once and return a cleaned script."""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(topic=topic)},
                ],
            )
        except ConnectionError as exc:
            raise OllamaConnectionError(
                "Cannot connect to Ollama. Is it running? (ollama serve)"
            ) from exc
        except Exception as exc:
            err = str(exc).lower()
            if "connection" in err or "refused" in err or "connect" in err:
                raise OllamaConnectionError(
                    "Cannot connect to Ollama. Is it running? (ollama serve)"
                ) from exc
            if "not found" in err or "model" in err:
                raise OllamaModelError(
                    f"Model '{self.model}' not available. Run: ollama pull {self.model}"
                ) from exc
            raise ScriptGeneratorError(f"Ollama request failed: {exc}") from exc

        message = response.get("message") or {}
        raw = (message.get("content") or "").strip()
        if not raw:
            raise ScriptGeneratorError("Ollama returned an empty response.")

        return self._clean_script(raw)

    def save(self, script: str) -> tuple[Path, Path]:
        """Save raw script for debugging and a formatted copy for reading."""
        raw_path = self.output_path
        formatted_path = self.formatted_path
        raw_body = script.strip() + "\n"
        formatted_body = clean_script_text(script)

        try:
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            formatted_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(raw_body, encoding="utf-8")
            formatted_path.write_text(formatted_body, encoding="utf-8")
        except OSError as exc:
            raise ScriptGeneratorError(f"Failed to save script: {exc}") from exc

        return raw_path.resolve(), formatted_path.resolve()

    def generate_and_save(self, topic: str) -> tuple[str, Path, Path]:
        """Generate a script and write debug + formatted files."""
        script = self.generate(topic)
        raw_path, formatted_path = self.save(script)
        return script, raw_path, formatted_path

    @staticmethod
    def _word_count(text: str) -> int:
        return len(text.split())

    def _clean_script(self, text: str) -> str:
        """Strip labels, directions, and other non-spoken artifacts."""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^(narrator|voiceover|host|speaker)\s*:\s*", "", line, flags=re.I)
            line = re.sub(r"^\[.*?\]\s*", "", line)
            line = re.sub(r"^\(.*?\)\s*", "", line)
            line = re.sub(r"^#+\s*", "", line)
            if line:
                lines.append(line)
        return " ".join(lines)

    def _validate_forbidden_content(self, script: str) -> None:
        """Reject scripts that contain labels, directions, or host references."""
        forbidden = [
            (r"\bnarrator\s*:", "narrator labels"),
            (r"\bvoiceover\s*:", "narrator labels"),
            (r"\[.*?\]", "scene directions in brackets"),
            (r"\bI(?:'m| am) your host\b", "host references"),
            (r"\bwelcome back to (?:the |my )?channel\b", "host references"),
        ]
        for pattern, label in forbidden:
            if re.search(pattern, script, re.I):
                raise ScriptValidationError(f"Script contains forbidden content: {label}.")
