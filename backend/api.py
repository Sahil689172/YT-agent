"""FastAPI layer exposing the AutoShorts pipeline to the frontend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.job_manager import JOBS_DIR, JobManager, JobStatus
from backend.logging_config import configure_logging
from backend.pipeline_runner import pipeline_worker

configure_logging()
logger = logging.getLogger(__name__)

job_manager = JobManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_manager.enqueue_runner(
        lambda job_id: pipeline_worker(job_id, job_manager)
    )
    logger.info("AutoShorts API started", extra={"event": "startup"})
    yield
    logger.info("AutoShorts API shutting down", extra={"event": "shutdown"})


app = FastAPI(
    title="AutoShorts API",
    description="REST API for the AutoShorts video generation pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / response models ---


class TopicGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="YouTube Shorts topic")


class ScriptGenerateRequest(BaseModel):
    script: str = Field(..., min_length=1, description="Custom narration script")
    topic: str = Field(
        default="Custom Script",
        description="Label used for metadata context",
    )


class JobStartedResponse(BaseModel):
    job_id: str
    status: str = "started"


class HealthResponse(BaseModel):
    status: str = "ok"


class ProgressResponse(BaseModel):
    job_id: str
    current_phase: str
    completed: int
    total: int
    status: str
    error: str | None = None


class ResultResponse(BaseModel):
    job_id: str
    status: str
    title: str | None = None
    description: str | None = None
    hashtags: str | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    script_path: str | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    detail: str


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/generate/topic",
    response_model=JobStartedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}},
)
def generate_from_topic(body: TopicGenerateRequest) -> JobStartedResponse:
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic cannot be empty.",
        )

    job = job_manager.create_topic_job(topic)
    logger.info(
        "Topic job created",
        extra={"job_id": job.job_id, "event": "job_created", "mode": "topic"},
    )
    return JobStartedResponse(job_id=job.job_id, status="started")


@app.post(
    "/generate/script",
    response_model=JobStartedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}},
)
def generate_from_script(body: ScriptGenerateRequest) -> JobStartedResponse:
    script = body.script.strip()
    if not script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Script cannot be empty.",
        )

    job = job_manager.create_script_job(script, topic=body.topic)
    logger.info(
        "Script job created",
        extra={"job_id": job.job_id, "event": "job_created", "mode": "script"},
    )
    return JobStartedResponse(job_id=job.job_id, status="started")


@app.get(
    "/progress/{job_id}",
    response_model=ProgressResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_progress(job_id: str) -> ProgressResponse:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    data = job.progress_dict()
    return ProgressResponse(
        job_id=data["job_id"],
        current_phase=data["current_phase"],
        completed=data["completed"],
        total=data["total"],
        status=_public_status(job.status),
        error=job.error,
    )


@app.get(
    "/result/{job_id}",
    response_model=ResultResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def get_result(job_id: str) -> ResultResponse:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job.status == JobStatus.FAILED:
        return ResultResponse(
            job_id=job_id,
            status="failed",
            error=job.error or "Pipeline failed.",
        )

    if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is not complete (status: {job.status.value}). Poll /progress/{job_id}.",
        )

    data = job.result_dict()
    return ResultResponse(
        job_id=job_id,
        status=data["status"],
        title=data.get("title"),
        description=data.get("description"),
        hashtags=data.get("hashtags"),
        video_path=data.get("video_path"),
        thumbnail_path=data.get("thumbnail_path"),
        script_path=data.get("script_path"),
    )


def _public_status(status: JobStatus) -> str:
    """Map internal status to API-facing progress status."""
    if status == JobStatus.RUNNING:
        return "running"
    if status == JobStatus.COMPLETED:
        return "completed"
    if status == JobStatus.FAILED:
        return "failed"
    if status == JobStatus.QUEUED:
        return "queued"
    return status.value


JOBS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/jobs", StaticFiles(directory=JOBS_DIR), name="jobs")
