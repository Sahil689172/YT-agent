"""YouTube metadata generation (title, description, hashtags) via local Ollama."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
SCRIPTS_DIR = Path("scripts")
TITLE_PATH = SCRIPTS_DIR / "title.txt"
DESCRIPTION_PATH = SCRIPTS_DIR / "description.txt"
HASHTAGS_PATH = SCRIPTS_DIR / "hashtags.txt"
HASHTAG_COUNT = 10

TITLE_SYSTEM = """You write YouTube Shorts titles.
Rules:
- One line only
- Catchy and clear, but NOT clickbait (no "you won't believe", "shocking", all-caps hype)
- Under 70 characters when possible
- Accurate to the script content
- No quotes around the title
- Output ONLY the title text"""

DESCRIPTION_SYSTEM = """You write YouTube video descriptions for Shorts.
Rules:
- Exactly 2 or 3 short paragraphs
- Separate paragraphs with a blank line
- Informative, friendly tone; no clickbait
- Reflect the script content accurately
- No hashtags in the description
- No section labels (e.g. "Description:")
- Output ONLY the description text"""

HASHTAGS_SYSTEM = """You suggest YouTube hashtags for Shorts.
Rules:
- Output exactly 10 hashtags
- One hashtag per line
- Each line starts with # (e.g. #Shorts)
- Relevant to the script topic and niche
- Mix of broad and specific tags
- No numbering, bullets, or extra commentary"""


class MetadataGeneratorError(Exception):
    """Base error for metadata generation."""


class MetadataOllamaConnectionError(MetadataGeneratorError):
    """Ollama is unreachable or not running."""


class MetadataOllamaModelError(MetadataGeneratorError):
    """Requested model is missing or failed."""


class MetadataValidationError(MetadataGeneratorError):
    """Generated metadata failed validation."""


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    description: str
    hashtags: list[str]


class MetadataGenerator:
    """Generate and persist YouTube title, description, and hashtags."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        title_path: Path | str = TITLE_PATH,
        description_path: Path | str = DESCRIPTION_PATH,
        hashtags_path: Path | str = HASHTAGS_PATH,
    ) -> None:
        self.model = model
        self.title_path = Path(title_path)
        self.description_path = Path(description_path)
        self.hashtags_path = Path(hashtags_path)

    def generate_title(self, script: str, topic: str) -> str:
        """Generate a YouTube title from script context."""
        logger.info("Generating YouTube title")
        prompt = (
            f"Topic: {topic}\n\n"
            f"Script:\n{script}\n\n"
            "Write one non-clickbait YouTube Shorts title for this video."
        )
        raw = self._chat(TITLE_SYSTEM, prompt)
        title = self._clean_single_line(raw)
        self._validate_title(title)
        logger.info("Title generated (%d chars)", len(title))
        return title

    def generate_description(self, script: str, topic: str) -> str:
        """Generate a 2-3 paragraph YouTube description from script context."""
        logger.info("Generating YouTube description")
        prompt = (
            f"Topic: {topic}\n\n"
            f"Script:\n{script}\n\n"
            "Write a 2-3 short paragraph YouTube description for this Short."
        )
        raw = self._chat(DESCRIPTION_SYSTEM, prompt)
        description = self._clean_description(raw)
        self._validate_description(description)
        logger.info("Description generated (%d paragraphs)", len(self._paragraphs(description)))
        return description

    def generate_hashtags(self, script: str, topic: str) -> list[str]:
        """Generate exactly 10 hashtags from script context."""
        logger.info("Generating hashtags")
        prompt = (
            f"Topic: {topic}\n\n"
            f"Script:\n{script}\n\n"
            f"Write exactly {HASHTAG_COUNT} relevant hashtags, one per line."
        )
        raw = self._chat(HASHTAGS_SYSTEM, prompt)
        hashtags = self._parse_hashtags(raw)
        self._validate_hashtags(hashtags)
        logger.info("Hashtags generated (%d tags)", len(hashtags))
        return hashtags

    def generate(self, script: str, topic: str) -> VideoMetadata:
        """Generate title, description, and hashtags using the script as context."""
        script = script.strip()
        topic = topic.strip()
        if not script:
            raise MetadataGeneratorError("Script cannot be empty.")
        if not topic:
            raise MetadataGeneratorError("Topic cannot be empty.")

        logger.info("Starting metadata generation for topic: %s", topic)
        title = self.generate_title(script, topic)
        description = self.generate_description(script, topic)
        hashtags = self.generate_hashtags(script, topic)
        return VideoMetadata(title=title, description=description, hashtags=hashtags)

    def save(self, metadata: VideoMetadata) -> tuple[Path, Path, Path]:
        """Write metadata files, creating the scripts directory if needed."""
        try:
            self.title_path.parent.mkdir(parents=True, exist_ok=True)
            self.title_path.write_text(metadata.title.strip() + "\n", encoding="utf-8")
            self.description_path.write_text(
                metadata.description.strip() + "\n", encoding="utf-8"
            )
            hashtag_body = "\n".join(metadata.hashtags) + "\n"
            self.hashtags_path.write_text(hashtag_body, encoding="utf-8")
        except OSError as exc:
            raise MetadataGeneratorError(f"Failed to save metadata: {exc}") from exc

        logger.info("Metadata saved to %s", self.title_path.parent.resolve())
        return (
            self.title_path.resolve(),
            self.description_path.resolve(),
            self.hashtags_path.resolve(),
        )

    def generate_and_save(self, script: str, topic: str) -> tuple[VideoMetadata, Path, Path, Path]:
        """Generate metadata and write title, description, and hashtag files."""
        metadata = self.generate(script, topic)
        paths = self.save(metadata)
        return metadata, *paths

    def _chat(self, system: str, user: str) -> str:
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except ConnectionError as exc:
            logger.error("Ollama connection failed")
            raise MetadataOllamaConnectionError(
                "Cannot connect to Ollama. Is it running? (ollama serve)"
            ) from exc
        except Exception as exc:
            err = str(exc).lower()
            if "connection" in err or "refused" in err or "connect" in err:
                logger.error("Ollama connection failed: %s", exc)
                raise MetadataOllamaConnectionError(
                    "Cannot connect to Ollama. Is it running? (ollama serve)"
                ) from exc
            if "not found" in err or "model" in err:
                logger.error("Ollama model error: %s", exc)
                raise MetadataOllamaModelError(
                    f"Model '{self.model}' not available. Run: ollama pull {self.model}"
                ) from exc
            logger.error("Ollama request failed: %s", exc)
            raise MetadataGeneratorError(f"Ollama request failed: {exc}") from exc

        message = response.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise MetadataGeneratorError("Ollama returned an empty response.")
        return content

    @staticmethod
    def _clean_single_line(text: str) -> str:
        line = text.strip().splitlines()[0].strip()
        line = re.sub(r'^["\']|["\']$', "", line)
        line = re.sub(r"^(title)\s*:\s*", "", line, flags=re.I)
        return line.strip()

    @staticmethod
    def _clean_description(text: str) -> str:
        text = re.sub(r"^(description)\s*:\s*", "", text.strip(), flags=re.I)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
        return "\n\n".join(paragraphs)

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        return [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]

    def _parse_hashtags(self, text: str) -> list[str]:
        tags: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^\d+[\).\s]+", "", line)
            for token in re.findall(r"#\w+", line):
                key = token.lower()
                if key not in seen:
                    seen.add(key)
                    tags.append(token if token[1:].islower() else token)
            if line.startswith("#") and line not in tags and line.lower() not in seen:
                seen.add(line.lower())
                tags.append(line)
            elif not line.startswith("#") and line.isidentifier():
                tag = f"#{line}"
                if tag.lower() not in seen:
                    seen.add(tag.lower())
                    tags.append(tag)
        return tags[:HASHTAG_COUNT]

    def _validate_title(self, title: str) -> None:
        if not title:
            raise MetadataValidationError("Title is empty.")
        clickbait_patterns = [
            r"you won'?t believe",
            r"shocking",
            r"gone wrong",
            r"insane",
            r"mind[- ]?blowing",
            r"!\s*!+",
        ]
        for pattern in clickbait_patterns:
            if re.search(pattern, title, re.I):
                raise MetadataValidationError(
                    f"Title appears clickbait ({pattern}): {title!r}"
                )

    def _validate_description(self, description: str) -> None:
        if not description:
            raise MetadataValidationError("Description is empty.")
        paragraphs = self._paragraphs(description)
        if len(paragraphs) < 2 or len(paragraphs) > 3:
            raise MetadataValidationError(
                f"Description must have 2-3 paragraphs; got {len(paragraphs)}."
            )

    def _validate_hashtags(self, hashtags: list[str]) -> None:
        if len(hashtags) != HASHTAG_COUNT:
            raise MetadataValidationError(
                f"Expected {HASHTAG_COUNT} hashtags; got {len(hashtags)}."
            )
        for tag in hashtags:
            if not tag.startswith("#") or len(tag) < 2:
                raise MetadataValidationError(f"Invalid hashtag format: {tag!r}")
