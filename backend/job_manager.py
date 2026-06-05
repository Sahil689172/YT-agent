"""In-memory job registry with queueing and artifact storage."""

from __future__ import annotations

import shutil
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = ROOT_DIR / "jobs"

# Standard output paths used by existing generators
TITLE_PATH = ROOT_DIR / "scripts" / "title.txt"
DESCRIPTION_PATH = ROOT_DIR / "scripts" / "description.txt"
VIDEO_PATH = ROOT_DIR / "videos" / "output.mp4"
SCRIPT_PATH = ROOT_DIR / "scripts" / "script.txt"

PHASES_TOPIC = [
    "Script Generation",
    "Metadata Generation",
    "Voice Generation",
    "Caption Generation",
    "Scene Generation",
    "Visual Timeline",
    "Finalization",
]

PHASES_SCRIPT = [
    "Script Preparation",
    "Metadata Generation",
    "Voice Generation",
    "Caption Generation",
    "Scene Generation",
    "Visual Timeline",
    "Finalization",
]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobResult:
    title: str = ""
    description: str = ""
    video_path: str = ""
    script_path: str = ""


@dataclass
class Job:
    job_id: str
    mode: str  # "topic" | "script"
    status: JobStatus = JobStatus.QUEUED
    phases: list[str] = field(default_factory=list)
    current_phase: str = "Queued"
    completed: int = 0
    total: int = 7
    topic: str = ""
    script: str = ""
    error: str | None = None
    result: JobResult | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    workspace: Path = field(default_factory=Path)
    phase_timings: list[dict[str, Any]] = field(default_factory=list)
    performance_summary: list[str] = field(default_factory=list)
    total_duration_seconds: float | None = None

    def progress_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "job_id": self.job_id,
            "current_phase": self.current_phase,
            "completed": self.completed,
            "total": self.total,
            "status": self.status.value,
        }
        if self.status == JobStatus.FAILED and self.error:
            data["error"] = self.error
        return data

    def result_dict(self) -> dict[str, Any]:
        if self.status != JobStatus.COMPLETED or not self.result:
            return {
                "job_id": self.job_id,
                "status": self.status.value,
                "error": self.error,
            }
        return {
            "job_id": self.job_id,
            "title": self.result.title,
            "description": self.result.description,
            "video_path": self.result.video_path,
            "script_path": self.result.script_path,
            "status": self.status.value,
        }


class JobManager:
    """Thread-safe job store with serialized pipeline execution."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._pipeline_lock = threading.Lock()
        self._queue: deque[str] = deque()
        self._worker_started = False

    def create_topic_job(self, topic: str) -> Job:
        job_id = self._new_id()
        workspace = JOBS_DIR / job_id
        job = Job(
            job_id=job_id,
            mode="topic",
            phases=list(PHASES_TOPIC),
            total=len(PHASES_TOPIC),
            topic=topic.strip(),
            workspace=workspace,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._queue.append(job_id)
        return job

    def create_script_job(self, script: str, topic: str = "Custom Script") -> Job:
        job_id = self._new_id()
        workspace = JOBS_DIR / job_id
        job = Job(
            job_id=job_id,
            mode="script",
            phases=list(PHASES_SCRIPT),
            total=len(PHASES_SCRIPT),
            script=script.strip(),
            topic=topic.strip() or "Custom Script",
            workspace=workspace,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._queue.append(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def enqueue_runner(self, runner: Callable[[str], None]) -> None:
        """Start background worker that drains the job queue."""
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True

        def worker() -> None:
            while True:
                job_id: str | None = None
                with self._lock:
                    if self._queue:
                        job_id = self._queue.popleft()
                if not job_id:
                    threading.Event().wait(0.5)
                    continue
                with self._pipeline_lock:
                    self._set_status(job_id, JobStatus.RUNNING)
                    try:
                        runner(job_id)
                    except Exception as exc:  # noqa: BLE001 — last-resort guard
                        self.fail(job_id, str(exc))

        thread = threading.Thread(target=worker, name="pipeline-worker", daemon=True)
        thread.start()

    def start_phase(self, job_id: str, phase: str, completed_before: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.current_phase = phase
            job.completed = completed_before
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def complete_phase(self, job_id: str, completed: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.completed = completed
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def update_performance(self, job_id: str, timer: Any) -> None:
        """Sync pipeline timer state into the job for progress polling."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.phase_timings = timer.to_dict_list()
            job.performance_summary = timer.summary_lines()
            job.total_duration_seconds = timer.total
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def complete(self, job_id: str, result: JobResult) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = JobStatus.COMPLETED
            job.current_phase = "Completed"
            job.completed = job.total
            job.result = result
            job.error = None
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def fail(self, job_id: str, error: str, phase: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = JobStatus.FAILED
            job.error = error
            if phase:
                job.current_phase = phase
            job.updated_at = datetime.now(timezone.utc).isoformat()

    def _set_status(self, job_id: str, status: JobStatus) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                if status == JobStatus.RUNNING:
                    job.current_phase = job.phases[0] if job.phases else "Running"
                job.updated_at = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex

    def finalize_artifacts(self, job_id: str) -> JobResult:
        """Copy pipeline outputs into the job workspace and build result payload."""
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Unknown job: {job_id}")

        workspace = job.workspace
        workspace.mkdir(parents=True, exist_ok=True)

        copies = [
            (TITLE_PATH, workspace / "title.txt"),
            (DESCRIPTION_PATH, workspace / "description.txt"),
            (SCRIPT_PATH, workspace / "script.txt"),
            (VIDEO_PATH, workspace / "output.mp4"),
        ]
        for src, dest in copies:
            if src.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        title = _read_text(workspace / "title.txt")
        if not title and TITLE_PATH.is_file():
            title = TITLE_PATH.read_text(encoding="utf-8")
        description = _read_text(workspace / "description.txt")
        if not description and DESCRIPTION_PATH.is_file():
            description = DESCRIPTION_PATH.read_text(encoding="utf-8")

        video_rel = f"jobs/{job_id}/output.mp4"
        script_rel = f"jobs/{job_id}/script.txt"

        if not (workspace / "output.mp4").is_file() and VIDEO_PATH.is_file():
            shutil.copy2(VIDEO_PATH, workspace / "output.mp4")

        _write_performance_file(job)

        return JobResult(
            title=title.strip(),
            description=description.strip(),
            video_path=video_rel.replace("\\", "/"),
            script_path=script_rel.replace("\\", "/"),
        )


def _read_text(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _write_performance_file(job: Job) -> None:
    """Persist timing summary beside job artifacts for later review."""
    if not job.performance_summary and not job.phase_timings:
        return
    lines: list[str] = ["AutoShorts — Pipeline performance", ""]
    if job.phase_timings:
        for entry in job.phase_timings:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label", "Phase")
            duration = entry.get("duration_seconds", 0)
            lines.append(f"{label}: {float(duration):.1f} sec")
            start = entry.get("start_time")
            end = entry.get("end_time")
            if start:
                lines.append(f"  START: {start}")
            if end:
                lines.append(f"  END: {end}")
            lines.append(f"  DURATION: {float(duration):.2f} sec")
            lines.append("")
    elif job.performance_summary:
        lines.extend(job.performance_summary)
        lines.append("")
    if job.total_duration_seconds is not None:
        lines.append(f"TOTAL: {job.total_duration_seconds:.1f} sec")
    job.workspace.mkdir(parents=True, exist_ok=True)
    perf_path = job.workspace / "performance.txt"
    perf_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
