"""YouTube Shorts script generation via local Ollama."""

from __future__ import annotations

import logging
import re
import textwrap
from pathlib import Path

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
TARGET_MIN_WORDS = 80
TARGET_MAX_WORDS = 100
MIN_WORDS = 80
MAX_WORDS = 100
MAX_REGENERATIONS = 3
MAX_GENERATION_ATTEMPTS = 1 + MAX_REGENERATIONS
DEFAULT_OUTPUT = Path("scripts/output.txt")
DEFAULT_FORMATTED = Path("scripts/script.txt")
WRAP_WIDTH = 90

# Lines to strip entirely (case-insensitive, matched at line start).
INTRO_LINE_PATTERNS = [
    r"^here\s+is\s+(?:your\s+)?(?:a\s+)?youtube\s+shorts?\s+script",
    r"^here'?s\s+(?:your\s+)?(?:a\s+)?youtube\s+shorts?\s+script",
    r"^here\s+is\s+(?:your\s+)?(?:a\s+)?script\b",
    r"^here'?s\s+(?:your\s+)?(?:a\s+)?script\b",
    r"^here'?s\s+a\s+script\s+for\b",
    r"^script\s*:",
    r"^title\s*:",
    r"^introduction\s*:",
]

# Phrases that must not appear anywhere in the final narration.
FORBIDDEN_PHRASE_PATTERNS = [
    (r"\bhere\s+is\s+(?:your\s+)?(?:a\s+)?script\b", "intro phrase 'here is ... script'"),
    (r"\bhere'?s\s+(?:your\s+)?(?:a\s+)?script\b", "intro phrase \"here's ... script\""),
    (r"\bhere'?s\s+a\s+script\s+for\s+(?:your\s+)?video\b", "intro phrase \"here's a script for your video\""),
    (r"\bhere\s+is\s+(?:a\s+)?youtube\s+shorts?\s+script\b", "intro phrase 'here is ... youtube shorts script'"),
    (r"\bhere'?s\s+(?:a\s+)?youtube\s+shorts?\s+script\b", "intro phrase \"here's ... youtube shorts script\""),
    (r"\bhere'?s\s+a\s+script\s+for\s+your\b", "intro phrase \"here's a script for your\""),
    (r"\bnarrator\s*:", "narrator labels"),
    (r"\bvoiceover\s*:", "narrator labels"),
    (r"\[.*?\]", "scene directions in brackets"),
    (r"\bI(?:'m| am) your host\b", "host references"),
    (r"\bwelcome back to (?:the |my )?channel\b", "host references"),
]

SYSTEM_PROMPT = f"""You write spoken-word scripts for YouTube Shorts.
Output ONLY the script text the speaker says aloud — nothing else.

Rules:
- Exactly {TARGET_MIN_WORDS} to {TARGET_MAX_WORDS} words (30-45 seconds when spoken aloud)
- Start immediately with the hook — the first spoken sentence must be about the topic
- NEVER include meta text such as:
  - "Here is your script"
  - "Here's a script"
  - "Here is a YouTube Shorts script"
  - "Script:" or "Title:" or "Introduction:"
- No narrator labels (e.g. Narrator:, Voiceover:)
- No scene directions or stage directions in brackets or parentheses
- No host references (e.g. "I'm your host", "welcome back to the channel")
- No titles, headings, bullet points, or metadata
- Conversational, punchy, strong close"""

USER_PROMPT_TEMPLATE = f"""Write a YouTube Shorts script about: {{topic}}

Plain spoken narration only. {TARGET_MIN_WORDS}-{TARGET_MAX_WORDS} words (30-45 seconds).
Do NOT include any introduction about writing a script — jump straight into the topic."""


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
        """Strip labels, directions, intro lines, and other non-spoken artifacts."""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if self._is_intro_line(line):
                logger.info("Removed intro line: %s", line[:80])
                continue
            line = re.sub(r"^(narrator|voiceover|host|speaker)\s*:\s*", "", line, flags=re.I)
            line = re.sub(r"^\[.*?\]\s*", "", line)
            line = re.sub(r"^\(.*?\)\s*", "", line)
            line = re.sub(r"^#+\s*", "", line)
            if line:
                lines.append(line)

        combined = " ".join(lines)
        combined = self._strip_intro_prefix(combined)
        return combined.strip()

    @staticmethod
    def _is_intro_line(line: str) -> bool:
        for pattern in INTRO_LINE_PATTERNS:
            if re.match(pattern, line, re.I):
                return True
        return False

    @staticmethod
    def _strip_intro_prefix(text: str) -> str:
        """Remove leading meta phrases sometimes prepended to the first sentence."""
        patterns = [
            r"^(?:here(?:'s|\s+is)\s+(?:your\s+)?(?:a\s+)?(?:youtube\s+shorts?\s+)?script(?:\s+about)?[:\s-]*)+",
            r"^(?:here(?:'s|\s+is)\s+(?:a\s+)?script(?:\s+for)?(?:\s+your)?(?:\s+video)?[:\s-]*)+",
            r"^(?:script|title|introduction)\s*:\s*",
        ]
        cleaned = text.strip()
        for pattern in patterns:
            updated = re.sub(pattern, "", cleaned, flags=re.I).strip()
            if updated != cleaned:
                cleaned = updated
        return cleaned

    def _validate_forbidden_content(self, script: str) -> None:
        """Reject scripts that contain intro/meta phrases or non-spoken artifacts."""
        for pattern, label in FORBIDDEN_PHRASE_PATTERNS:
            if re.search(pattern, script, re.I):
                raise ScriptValidationError(f"Script contains forbidden content: {label}.")
