"""YouTube metadata generation (title, description, hashtags) via local Ollama."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
SCRIPTS_DIR = Path("scripts")
TITLE_PATH = SCRIPTS_DIR / "title.txt"
DESCRIPTION_PATH = SCRIPTS_DIR / "description.txt"
HASHTAG_COUNT = 10
HASHTAGS_PER_LINE = 5
MAX_SCRIPT_CHARS_IN_PROMPT = 3500

COMBINED_SYSTEM = """You write YouTube Shorts metadata in one response.
Rules:
- Output exactly three labeled sections: TITLE, DESCRIPTION, HASHTAGS
- TITLE: one line, catchy but not clickbait, under 70 characters, no quotes
- DESCRIPTION: 2 or 3 short paragraphs only (never 4+), separated by a blank line, no hashtags
- HASHTAGS: exactly 10 tags, each starting with #; relevant to topic, script content, and niche/category (e.g. finance → #finance #investing; coding → #coding #programming; AI → #ai #aitools)
- No extra commentary outside the three sections"""

COMBINED_USER_TEMPLATE = """Topic: {topic}

Script:
{script}

Respond in this exact format:

TITLE:
<one line title>

DESCRIPTION:
<paragraph 1>

<paragraph 2>

HASHTAGS:
#tag1
#tag2
(... exactly 10 hashtags, one per line)"""

# Legacy prompts kept for optional individual generators / tests
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
- Relevant to the script topic, video content, and category/niche
- Mix of broad and specific tags (e.g. finance: #finance #investing; coding: #coding #programming; AI: #ai #aitools)
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


def _script_for_prompt(script: str, max_chars: int = MAX_SCRIPT_CHARS_IN_PROMPT) -> str:
    script = script.strip()
    if len(script) <= max_chars:
        return script
    logger.info(
        "Metadata prompt: using first %d chars of script (%d total)",
        max_chars,
        len(script),
    )
    return script[:max_chars].rsplit(" ", 1)[0] + "…"


class MetadataGenerator:
    """Generate and persist YouTube title, description, and hashtags."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        title_path: Path | str = TITLE_PATH,
        description_path: Path | str = DESCRIPTION_PATH,
    ) -> None:
        self.model = model
        self.title_path = Path(title_path)
        self.description_path = Path(description_path)

    def generate_title(self, script: str, topic: str) -> str:
        """Generate a YouTube title from script context (legacy single-field call)."""
        return self.generate(script, topic).title

    def generate_description(self, script: str, topic: str) -> str:
        """Generate description (legacy single-field call)."""
        return self.generate(script, topic).description

    def generate_hashtags(self, script: str, topic: str) -> list[str]:
        """Generate hashtags (legacy single-field call)."""
        return self.generate(script, topic).hashtags

    def generate(self, script: str, topic: str) -> VideoMetadata:
        """Generate title, description, and hashtags in one Ollama request."""
        script = script.strip()
        topic = topic.strip()
        if not script:
            raise MetadataGeneratorError("Script cannot be empty.")
        if not topic:
            raise MetadataGeneratorError("Topic cannot be empty.")

        logger.info(
            "Starting metadata generation (single Ollama call) for topic: %s",
            topic,
        )
        started = time.perf_counter()
        prompt = COMBINED_USER_TEMPLATE.format(
            topic=topic,
            script=_script_for_prompt(script),
        )

        last_validation_error: MetadataValidationError | None = None
        for attempt in range(1, 3):
            try:
                raw = self._chat(COMBINED_SYSTEM, prompt)
                title, description, hashtags = self._parse_combined_response(raw)
                description = self._normalize_description(description)
                self._validate_title(title)
                self._validate_description(description)
                self._validate_hashtags(hashtags)
                elapsed = time.perf_counter() - started
                logger.info(
                    "Metadata generated in one call (%.2f sec, attempt %d): title=%d chars, "
                    "%d paragraphs, %d hashtags",
                    elapsed,
                    attempt,
                    len(title),
                    len(self._paragraphs(description)),
                    len(hashtags),
                )
                return VideoMetadata(
                    title=title, description=description, hashtags=hashtags
                )
            except MetadataValidationError as exc:
                last_validation_error = exc
                logger.warning(
                    "Metadata validation failed (attempt %d/2): %s",
                    attempt,
                    exc,
                )

        assert last_validation_error is not None
        raise last_validation_error

    def save(self, metadata: VideoMetadata) -> tuple[Path, Path]:
        """Write title.txt and description.txt (hashtags appended to description)."""
        try:
            self.title_path.parent.mkdir(parents=True, exist_ok=True)
            self.title_path.write_text(metadata.title.strip() + "\n", encoding="utf-8")
            self.description_path.write_text(
                self._compose_description_file(metadata.description, metadata.hashtags),
                encoding="utf-8",
            )
        except OSError as exc:
            raise MetadataGeneratorError(f"Failed to save metadata: {exc}") from exc

        logger.info("Metadata saved to %s", self.title_path.parent.resolve())
        return (
            self.title_path.resolve(),
            self.description_path.resolve(),
        )

    def generate_and_save(self, script: str, topic: str) -> tuple[VideoMetadata, Path, Path]:
        """Generate metadata and write title + description (with hashtags) files."""
        metadata = self.generate(script, topic)
        paths = self.save(metadata)
        return metadata, *paths

    @staticmethod
    def _format_hashtag_block(hashtags: list[str]) -> str:
        """Format 10 hashtags as two lines of five, space-separated."""
        line1 = " ".join(hashtags[:HASHTAGS_PER_LINE])
        line2 = " ".join(hashtags[HASHTAGS_PER_LINE:HASHTAG_COUNT])
        return f"{line1}\n{line2}"

    def _compose_description_file(self, body: str, hashtags: list[str]) -> str:
        """Build description.txt: paragraphs, blank line, then hashtag block."""
        return f"{body.strip()}\n\n{self._format_hashtag_block(hashtags)}\n"

    def _parse_combined_response(self, raw: str) -> tuple[str, str, list[str]]:
        text = raw.strip()
        title_match = re.search(
            r"TITLE:\s*(.+?)(?=\n\s*DESCRIPTION:|\Z)",
            text,
            re.I | re.S,
        )
        desc_match = re.search(
            r"DESCRIPTION:\s*(.+?)(?=\n\s*HASHTAGS:|\Z)",
            text,
            re.I | re.S,
        )
        tags_match = re.search(r"HASHTAGS:\s*(.+)", text, re.I | re.S)

        if not title_match or not desc_match or not tags_match:
            logger.warning(
                "Combined metadata missing section headers; falling back to line parsing"
            )
            return self._parse_combined_fallback(text)

        title = self._clean_single_line(title_match.group(1).strip())
        description = self._clean_description(desc_match.group(1).strip())
        hashtags = self._parse_hashtags(tags_match.group(1).strip())
        return title, description, hashtags

    def _parse_combined_fallback(self, text: str) -> tuple[str, str, list[str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 3:
            raise MetadataValidationError(
                "Could not parse TITLE / DESCRIPTION / HASHTAGS from model output."
            )
        title = self._clean_single_line(lines[0])
        tag_start = next(
            (index for index, line in enumerate(lines) if line.startswith("#")),
            len(lines),
        )
        hashtags = self._parse_hashtags("\n".join(lines[tag_start:]))
        body_lines = lines[1:tag_start]
        description = self._clean_description("\n\n".join(body_lines))
        return title, description, hashtags

    def _chat(self, system: str, user: str) -> str:
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                options={"num_predict": 900, "temperature": 0.4},
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
        if not paragraphs:
            paragraphs = [line for line in text.splitlines() if line.strip()]
        return "\n\n".join(paragraphs)

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        return [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]

    def _normalize_description(self, description: str) -> str:
        """Coerce description to 2–3 paragraphs without failing on minor LLM formatting drift."""
        paragraphs = self._paragraphs(description)

        while len(paragraphs) > 3:
            merge_at = 0
            merge_len = float("inf")
            for i in range(len(paragraphs) - 1):
                combined = len(paragraphs[i]) + len(paragraphs[i + 1])
                if combined < merge_len:
                    merge_len = combined
                    merge_at = i
            paragraphs[merge_at] = f"{paragraphs[merge_at]} {paragraphs[merge_at + 1]}".strip()
            del paragraphs[merge_at + 1]
            logger.info(
                "Description normalized: merged paragraphs down to %d",
                len(paragraphs),
            )

        if len(paragraphs) == 1:
            sentences = re.split(r"(?<=[.!?])\s+", paragraphs[0].strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            if len(sentences) >= 2:
                mid = len(sentences) // 2
                first = " ".join(sentences[:mid]).strip()
                second = " ".join(sentences[mid:]).strip()
                if first and second:
                    paragraphs = [first, second]
                    logger.info("Description normalized: split single block into 2 paragraphs")

        return "\n\n".join(paragraphs)

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
        if re.search(r"#\w+", description):
            raise MetadataValidationError(
                "Description must not contain hashtags (they are appended on save)."
            )
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
