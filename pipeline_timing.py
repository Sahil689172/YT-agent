"""Pipeline phase timing and profiling."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Display labels (terminal, API, frontend summary)
PHASE_SCRIPT_GENERATION = "Script Generation"
PHASE_SCRIPT_PREPARATION = "Script Preparation"
PHASE_METADATA = "Metadata Generation"
PHASE_VOICE = "Voice Generation"
PHASE_CAPTIONS = "Caption Generation"
PHASE_SCENES = "Scene Agent"
PHASE_ASSET_SEARCH = "Asset Search"
PHASE_VIDEO = "Video Rendering"
PHASE_THUMBNAIL = "Thumbnail Generation"
PHASE_FINALIZATION = "Finalization"

# Backward-compatible aliases used by main.py imports
PHASE_SCRIPT = PHASE_SCRIPT_GENERATION

OPTIMIZATION_TARGETS_SEC = {
    PHASE_METADATA: 15,
    PHASE_SCENES: 20,
    PHASE_ASSET_SEARCH: 30,
    "Total": 180,
}

# Preferred summary order (sub-phases before coarse Visual Timeline bucket)
SUMMARY_ORDER: tuple[str, ...] = (
    PHASE_SCRIPT_GENERATION,
    PHASE_SCRIPT_PREPARATION,
    PHASE_METADATA,
    PHASE_VOICE,
    PHASE_CAPTIONS,
    PHASE_SCENES,
    PHASE_ASSET_SEARCH,
    PHASE_VIDEO,
    PHASE_THUMBNAIL,
    PHASE_FINALIZATION,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds")


def log_optimization_banner() -> None:
    """Print/log active performance optimizations for before/after comparison."""
    lines = [
        "",
        "Performance optimization sprint — active settings:",
        "  • Metadata: 1 Ollama call (TITLE + DESCRIPTION + HASHTAGS)",
        "  • Scene Agent: 1 Ollama call per attempt (max 2 attempts), truncated script prompt",
        "  • Asset Search: parallel scenes, early-exit API search, 12 workers / 10 downloads",
        "  • Thumbnail: reuses timeline assets or video frame (no new stock searches)",
        "  Targets: Metadata <15s | Scenes <20s | Assets <30s | Total <180s",
        "─" * 48,
    ]
    block = "\n".join(lines)
    print(block, flush=True)
    logger.info(
        "Performance optimizations enabled",
        extra={"event": "perf_optimization_sprint"},
    )


@dataclass(frozen=True)
class PhaseTiming:
    """Wall-clock timing for one pipeline phase."""

    label: str
    start_time: str
    end_time: str
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.duration_seconds, 2),
        }

    def summary_line(self) -> str:
        return f"{self.label}: {self.duration_seconds:.1f} sec"


@dataclass
class PipelineTimer:
    """Accumulates per-phase timings with start/end timestamps."""

    _records: dict[str, PhaseTiming] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    @contextmanager
    def track(self, phase: str) -> Iterator[None]:
        start_dt = _utc_now()
        start_perf = time.perf_counter()
        logger.info(
            "PERF %s — START %s",
            phase,
            _format_ts(start_dt),
            extra={"perf_phase": phase, "perf_event": "start", "perf_start": _format_ts(start_dt)},
        )
        print(f"[timing] {phase} — START {_format_ts(start_dt)}", flush=True)
        try:
            yield
        finally:
            end_dt = _utc_now()
            elapsed = time.perf_counter() - start_perf
            self._store(phase, _format_ts(start_dt), _format_ts(end_dt), elapsed)
            self._log_phase_complete(phase, _format_ts(start_dt), _format_ts(end_dt), elapsed)

    def add(self, phase: str, seconds: float) -> None:
        """Record duration for work already measured (e.g. asset search split)."""
        if seconds < 0:
            seconds = 0.0
        end_dt = _utc_now()
        start_dt = end_dt.timestamp() - seconds
        start_iso = _format_ts(datetime.fromtimestamp(start_dt, tz=timezone.utc))
        end_iso = _format_ts(end_dt)
        self._store(phase, start_iso, end_iso, seconds)
        self._log_phase_complete(phase, start_iso, end_iso, seconds)

    def _store(
        self,
        phase: str,
        start_iso: str,
        end_iso: str,
        elapsed: float,
    ) -> None:
        if phase not in self._order:
            self._order.append(phase)
        self._records[phase] = PhaseTiming(
            label=phase,
            start_time=start_iso,
            end_time=end_iso,
            duration_seconds=elapsed,
        )

    @staticmethod
    def _log_phase_complete(
        phase: str,
        start_iso: str,
        end_iso: str,
        elapsed: float,
    ) -> None:
        logger.info(
            "PERF %s — END %s — DURATION %.2f sec",
            phase,
            end_iso,
            elapsed,
            extra={
                "perf_phase": phase,
                "perf_event": "end",
                "perf_start": start_iso,
                "perf_end": end_iso,
                "perf_duration_sec": round(elapsed, 2),
            },
        )
        print(
            f"[timing] {phase} — END {end_iso} — DURATION {elapsed:.2f} sec",
            flush=True,
        )

    def get(self, phase: str) -> float:
        record = self._records.get(phase)
        return record.duration_seconds if record else 0.0

    @property
    def total(self) -> float:
        return sum(r.duration_seconds for r in self._records.values())

    def ordered_records(self) -> list[PhaseTiming]:
        seen: set[str] = set()
        ordered: list[PhaseTiming] = []
        for label in SUMMARY_ORDER:
            if label in self._records:
                ordered.append(self._records[label])
                seen.add(label)
        for label in self._order:
            if label not in seen and label in self._records:
                ordered.append(self._records[label])
        return ordered

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.ordered_records()]

    def summary_lines(self) -> list[str]:
        lines = [r.summary_line() for r in self.ordered_records()]
        if lines:
            lines.append(f"TOTAL: {self.total:.1f} sec")
        return lines

    def log_summary(self) -> None:
        records = self.ordered_records()
        if not records:
            return

        lines = ["", "Performance summary:", "─" * 40]
        for record in records:
            lines.append(f"  {record.summary_line()}")
            lines.append(f"    START:    {record.start_time}")
            lines.append(f"    END:      {record.end_time}")
            lines.append(f"    DURATION: {record.duration_seconds:.2f} sec")
        lines.append("─" * 40)
        lines.append(f"  TOTAL: {self.total:.1f} sec")
        lines.append("")
        lines.append("  Targets (optimization sprint):")
        for label, target in OPTIMIZATION_TARGETS_SEC.items():
            actual = self.total if label == "Total" else self.get(label)
            status = "OK" if actual <= target else "OVER"
            lines.append(f"    {label}: {actual:.1f}s / {target}s [{status}]")
        block = "\n".join(lines)
        print(block, flush=True)

        compact = ", ".join(r.summary_line() for r in records)
        logger.info(
            "Pipeline performance — TOTAL %.2f sec — %s",
            self.total,
            compact,
            extra={
                "perf_event": "summary",
                "perf_total_sec": round(self.total, 2),
                "perf_phases": self.to_dict_list(),
            },
        )
