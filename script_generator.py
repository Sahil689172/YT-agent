"""YouTube Shorts script generation via local Ollama."""

from __future__ import annotations

import re
from pathlib import Path

import ollama

DEFAULT_MODEL = "llama3"
MIN_WORDS = 80
MAX_WORDS = 120
DEFAULT_OUTPUT = Path("scripts/output.txt")

SYSTEM_PROMPT = """You write spoken-word scripts for YouTube Shorts.
Output ONLY the script text the speaker says aloud.
Rules:
- 80 to 120 words total
- No narrator labels (e.g. Narrator:, Voiceover:)
- No scene directions or stage directions in brackets or parentheses
- No host references (e.g. "I'm your host", "welcome back to the channel")
- No titles, headings, bullet points, or metadata
- Conversational, punchy, hook in the first line, strong close"""

USER_PROMPT_TEMPLATE = """Write a YouTube Shorts script about: {topic}

Remember: plain spoken script only, 80-120 words."""


class ScriptGeneratorError(Exception):
    """Base error for script generation."""


class OllamaConnectionError(ScriptGeneratorError):
    """Ollama is unreachable or not running."""


class OllamaModelError(ScriptGeneratorError):
    """Requested model is missing or failed."""


class ScriptValidationError(ScriptGeneratorError):
    """Generated script failed length or format checks."""


class ScriptGenerator:
    """Generate and persist YouTube Shorts scripts using Ollama."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        output_path: Path | str = DEFAULT_OUTPUT,
        min_words: int = MIN_WORDS,
        max_words: int = MAX_WORDS,
    ) -> None:
        self.model = model
        self.output_path = Path(output_path)
        self.min_words = min_words
        self.max_words = max_words

    def generate(self, topic: str) -> str:
        """Generate a script for the given topic."""
        topic = topic.strip()
        if not topic:
            raise ScriptGeneratorError("Topic cannot be empty.")

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

        script = self._clean_script(raw)
        self._validate_script(script)
        return script

    def save(self, script: str, path: Path | str | None = None) -> Path:
        """Write script to disk, creating parent directories if needed."""
        target = Path(path) if path is not None else self.output_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(script.strip() + "\n", encoding="utf-8")
        except OSError as exc:
            raise ScriptGeneratorError(f"Failed to save script to {target}: {exc}") from exc
        return target.resolve()

    def generate_and_save(self, topic: str, path: Path | str | None = None) -> tuple[str, Path]:
        """Generate a script and write it to the output file."""
        script = self.generate(topic)
        saved_path = self.save(script, path)
        return script, saved_path

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

    def _validate_script(self, script: str) -> None:
        """Ensure word count and forbidden patterns."""
        count = self._word_count(script)
        if count < self.min_words or count > self.max_words:
            raise ScriptValidationError(
                f"Script length is {count} words; expected {self.min_words}-{self.max_words}."
            )

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
