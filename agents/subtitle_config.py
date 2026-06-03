"""YouTube Shorts subtitle styling and segmentation configuration."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
MAX_WIDTH_RATIO = 0.8

FONT_PREFERENCES = (
    "Poppins SemiBold",
    "Montserrat SemiBold",
    "Inter Bold",
    "Roboto Medium",
    "Arial",
)

DEFAULT_FONT_SIZE = 13
DEFAULT_MAX_LINES = 2
DEFAULT_BOTTOM_MARGIN = 110
DEFAULT_MIN_WORDS = 3
DEFAULT_MAX_WORDS = 6
DEFAULT_TARGET_WORDS = 5

# ~35% smaller than legacy FontSize=20
LEGACY_FONT_SIZE = 20


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %d", name, raw, default)
        return default


def subtitle_font_name() -> str:
    custom = os.environ.get("SUBTITLE_FONT_NAME", "").strip()
    return custom or FONT_PREFERENCES[0]


def subtitle_font_size() -> int:
    return max(8, _env_int("SUBTITLE_FONT_SIZE", DEFAULT_FONT_SIZE))


def subtitle_max_lines() -> int:
    return max(1, min(3, _env_int("SUBTITLE_MAX_LINES", DEFAULT_MAX_LINES)))


def subtitle_bottom_margin() -> int:
    return max(40, _env_int("SUBTITLE_BOTTOM_MARGIN", DEFAULT_BOTTOM_MARGIN))


def subtitle_min_words() -> int:
    return max(1, _env_int("SUBTITLE_MIN_WORDS", DEFAULT_MIN_WORDS))


def subtitle_max_words() -> int:
    return max(subtitle_min_words(), _env_int("SUBTITLE_MAX_WORDS", DEFAULT_MAX_WORDS))


def subtitle_horizontal_margin() -> int:
    """Side margins so text stays within 80% of frame width."""
    return int(VIDEO_WIDTH * (1 - MAX_WIDTH_RATIO) / 2)


def build_subtitle_force_style() -> str:
    """
    ASS force_style for FFmpeg subtitles filter — Shorts/Reels style.

    White text, black outline, semi-transparent dark box, bottom-center.
    """
    margin_h = subtitle_horizontal_margin()
    # BorderStyle 4 = outline + shadow + background box
    # BackColour alpha: 00 opaque, higher = more transparent in ASS
    return (
        f"FontName={subtitle_font_name()},"
        f"FontSize={subtitle_font_size()},"
        "Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BackColour=&H80000000,"
        "BorderStyle=4,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        f"MarginV={subtitle_bottom_margin()},"
        f"MarginL={margin_h},"
        f"MarginR={margin_h},"
        "WrapStyle=0"
    )


# Kept as module-level string for backward-compatible imports; rebuilt on import.
SUBTITLE_FORCE_STYLE = build_subtitle_force_style()


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


def _estimate_max_chars_per_line(font_size: int) -> int:
    """Rough character budget per line at 80% frame width."""
    usable = int(VIDEO_WIDTH * MAX_WIDTH_RATIO)
    return max(12, int(usable / (font_size * 0.55)))


def _split_text_to_lines(text: str, max_lines: int, max_chars_per_line: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if len(trial) <= max_chars_per_line:
            current.append(word)
        elif current:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines:
                break
        else:
            lines.append(word[:max_chars_per_line])
            current = []
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines[:max_lines]


def _format_cue_text(words: list[str], max_lines: int) -> str | None:
    text = " ".join(w.strip() for w in words if w.strip())
    if not text:
        return None
    max_chars = _estimate_max_chars_per_line(subtitle_font_size())
    lines = _split_text_to_lines(text, max_lines, max_chars)
    if not lines:
        return None
    return "\n".join(lines)


def _collect_words(result: dict) -> list[dict[str, float | str]]:
    words: list[dict[str, float | str]] = []
    for segment in result.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        seg_words = segment.get("words")
        if isinstance(seg_words, list) and seg_words:
            for item in seg_words:
                if not isinstance(item, dict):
                    continue
                token = str(item.get("word") or "").strip()
                if not token:
                    continue
                try:
                    start = float(item["start"])
                    end = float(item["end"])
                except (KeyError, TypeError, ValueError):
                    continue
                if end > start:
                    words.append({"word": token, "start": start, "end": end})
            continue

        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        try:
            seg_start = float(segment["start"])
            seg_end = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        tokens = text.split()
        if not tokens or seg_end <= seg_start:
            continue
        step = (seg_end - seg_start) / len(tokens)
        for index, token in enumerate(tokens):
            w_start = seg_start + index * step
            w_end = w_start + step
            words.append({"word": token, "start": w_start, "end": w_end})

    return words


def _pack_word_count(remaining: int, min_words: int, max_words: int, target: int) -> int:
    if remaining <= max_words:
        return remaining
    if remaining <= max_words + min_words - 1:
        first = remaining // 2
        return max(min_words, min(max_words, first))
    return max(min_words, min(max_words, target))


def segment_captions_for_shorts(result: dict) -> list[SubtitleCue]:
    """
    Split Whisper output into short, mobile-friendly cues (3–6 words, max 2 lines).
    """
    words = _collect_words(result)
    if not words:
        return []

    min_words = subtitle_min_words()
    max_words = subtitle_max_words()
    target = DEFAULT_TARGET_WORDS
    max_lines = subtitle_max_lines()

    cues: list[SubtitleCue] = []
    index = 0
    while index < len(words):
        remaining = len(words) - index
        count = _pack_word_count(remaining, min_words, max_words, target)
        chunk = words[index : index + count]
        index += count

        tokens = [str(w["word"]) for w in chunk]
        text = _format_cue_text(tokens, max_lines)
        if not text:
            continue

        start = float(chunk[0]["start"])
        end = float(chunk[-1]["end"])
        if end <= start:
            end = start + 0.05

        cues.append(SubtitleCue(start=start, end=end, text=text))

    return _merge_tiny_gaps(cues)


def _merge_tiny_gaps(cues: list[SubtitleCue], gap_threshold: float = 0.04) -> list[SubtitleCue]:
    if len(cues) < 2:
        return cues
    merged: list[SubtitleCue] = [cues[0]]
    max_words = subtitle_max_words()
    max_lines = subtitle_max_lines()

    for cue in cues[1:]:
        prev = merged[-1]
        gap = cue.start - prev.end
        prev_words = len(prev.text.replace("\n", " ").split())
        cue_words = len(cue.text.replace("\n", " ").split())
        if (
            gap < gap_threshold
            and prev_words + cue_words <= max_words
            and "\n" not in prev.text
            and "\n" not in cue.text
        ):
            combined = f"{prev.text} {cue.text}"
            lines = _split_text_to_lines(
                combined,
                max_lines,
                _estimate_max_chars_per_line(subtitle_font_size()),
            )
            if len(lines) <= max_lines:
                merged[-1] = SubtitleCue(
                    start=prev.start,
                    end=cue.end,
                    text="\n".join(lines),
                )
                continue
        merged.append(cue)

    return merged


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_shorts_srt(cues: list[SubtitleCue], output_path: str | Path) -> None:
    from pathlib import Path

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        start = format_srt_timestamp(cue.start)
        end = format_srt_timestamp(cue.end)
        blocks.append(f"{index}\n{start} --> {end}\n{cue.text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
    logger.info(
        "Wrote %d Shorts-style cues to %s (font=%s, size=%d, max_lines=%d)",
        len(cues),
        path,
        subtitle_font_name(),
        subtitle_font_size(),
        subtitle_max_lines(),
    )


def log_subtitle_settings() -> None:
    logger.info(
        "Subtitle settings: font=%s size=%d max_lines=%d margin_v=%d "
        "words=%d-%d width=%.0f%%",
        subtitle_font_name(),
        subtitle_font_size(),
        subtitle_max_lines(),
        subtitle_bottom_margin(),
        subtitle_min_words(),
        subtitle_max_words(),
        MAX_WIDTH_RATIO * 100,
    )
