"""Run the existing AutoShorts pipeline for API jobs (no generator rewrites)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

from backend.job_manager import JobManager
from backend.logging_config import phase_logger

ROOT_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Pipeline step failed with a user-facing message."""

    def __init__(self, message: str, phase: str) -> None:
        super().__init__(message)
        self.phase = phase


def run_job(job_id: str, job_manager: JobManager) -> None:
    """Execute pipeline for a job (called under pipeline lock)."""
    job = job_manager.get(job_id)
    if not job:
        raise PipelineError(f"Job not found: {job_id}", "Initialization")

    os.chdir(ROOT_DIR)

    if job.mode == "topic":
        _run_topic_pipeline(job_id, job.topic, job_manager)
    elif job.mode == "script":
        _run_script_pipeline(job_id, job.script, job.topic, job_manager)
    else:
        raise PipelineError(f"Unknown job mode: {job.mode}", "Initialization")


def _run_topic_pipeline(job_id: str, topic: str, jm: JobManager) -> None:
    from script_generator import ScriptGenerator

    phases = jm.get(job_id).phases  # type: ignore[union-attr]
    script_generator = ScriptGenerator()
    script = ""
    completed = 0

    def step(phase: str, fn: Callable[[], None]) -> None:
        nonlocal completed
        jm.start_phase(job_id, phase, completed)
        log = phase_logger(__name__, job_id, phase)
        log.info("Started", extra={"event": "started"})
        try:
            fn()
        except Exception as exc:
            log.error("Failed", extra={"event": "failed", "error": str(exc)})
            raise PipelineError(str(exc), phase) from exc
        completed += 1
        jm.complete_phase(job_id, completed)
        log.info("Completed", extra={"event": "completed"})

    step(phases[0], lambda: _phase_script_topic(script_generator, topic))
    script = _read_script()

    step(phases[1], lambda: _phase_metadata(script, topic))
    step(phases[2], lambda: _phase_voice())
    step(phases[3], lambda: _phase_captions())
    step(phases[4], lambda: _phase_scenes())
    step(phases[5], lambda: _phase_visual_timeline())
    step(phases[6], lambda: _phase_thumbnail())
    step(phases[7], lambda: None)  # Finalization marker

    result = jm.finalize_artifacts(job_id)
    jm.complete(job_id, result)
    logger.info(
        "Job completed",
        extra={"job_id": job_id, "event": "job_completed", "mode": "topic"},
    )


def _run_script_pipeline(job_id: str, script_text: str, topic: str, jm: JobManager) -> None:
    from script_generator import ScriptGenerator

    phases = jm.get(job_id).phases  # type: ignore[union-attr]
    script_generator = ScriptGenerator()
    completed = 0

    def step(phase: str, fn: Callable[[], None]) -> None:
        nonlocal completed
        jm.start_phase(job_id, phase, completed)
        log = phase_logger(__name__, job_id, phase)
        log.info("Started", extra={"event": "started"})
        try:
            fn()
        except Exception as exc:
            log.error("Failed", extra={"event": "failed", "error": str(exc)})
            raise PipelineError(str(exc), phase) from exc
        completed += 1
        jm.complete_phase(job_id, completed)
        log.info("Completed", extra={"event": "completed"})

    step(phases[0], lambda: _phase_script_custom(script_generator, script_text))
    script = _read_script()

    step(phases[1], lambda: _phase_metadata(script, topic))
    step(phases[2], lambda: _phase_voice())
    step(phases[3], lambda: _phase_captions())
    step(phases[4], lambda: _phase_scenes())
    step(phases[5], lambda: _phase_visual_timeline())
    step(phases[6], lambda: _phase_thumbnail())
    step(phases[7], lambda: None)

    result = jm.finalize_artifacts(job_id)
    jm.complete(job_id, result)
    logger.info(
        "Job completed",
        extra={"job_id": job_id, "event": "job_completed", "mode": "script"},
    )


def _phase_script_topic(script_generator, topic: str) -> None:
    from script_generator import (
        OllamaConnectionError,
        OllamaModelError,
        ScriptGeneratorError,
        ScriptValidationError,
    )

    try:
        script_generator.generate_and_save(topic)
    except OllamaConnectionError as exc:
        raise PipelineError(str(exc), "Script Generation") from exc
    except OllamaModelError as exc:
        raise PipelineError(str(exc), "Script Generation") from exc
    except ScriptValidationError as exc:
        raise PipelineError(str(exc), "Script Generation") from exc
    except ScriptGeneratorError as exc:
        raise PipelineError(str(exc), "Script Generation") from exc


def _phase_script_custom(script_generator, script_text: str) -> None:
    from script_generator import ScriptGeneratorError

    if not script_text.strip():
        raise PipelineError("Script cannot be empty.", "Script Preparation")
    try:
        script_generator.save(script_text)
    except ScriptGeneratorError as exc:
        raise PipelineError(str(exc), "Script Preparation") from exc


def _phase_metadata(script: str, topic: str) -> None:
    from metadata_generator import (
        MetadataGenerator,
        MetadataGeneratorError,
        MetadataOllamaConnectionError,
        MetadataOllamaModelError,
        MetadataValidationError,
    )

    metadata_generator = MetadataGenerator()
    try:
        metadata_generator.generate_and_save(script, topic)
    except MetadataOllamaConnectionError as exc:
        raise PipelineError(str(exc), "Metadata Generation") from exc
    except MetadataOllamaModelError as exc:
        raise PipelineError(str(exc), "Metadata Generation") from exc
    except MetadataValidationError as exc:
        raise PipelineError(str(exc), "Metadata Generation") from exc
    except MetadataGeneratorError as exc:
        raise PipelineError(str(exc), "Metadata Generation") from exc


def _phase_voice() -> None:
    from voice_generator import (
        PiperNotFoundError,
        ScriptNotFoundError,
        VoiceGenerationError,
        VoiceGenerator,
        VoiceGeneratorError,
        VoiceModelNotFoundError,
    )

    voice_generator = VoiceGenerator()
    try:
        voice_generator.generate()
    except PiperNotFoundError as exc:
        raise PipelineError(str(exc), "Voice Generation") from exc
    except VoiceModelNotFoundError as exc:
        raise PipelineError(str(exc), "Voice Generation") from exc
    except ScriptNotFoundError as exc:
        raise PipelineError(str(exc), "Voice Generation") from exc
    except VoiceGenerationError as exc:
        raise PipelineError(str(exc), "Voice Generation") from exc
    except VoiceGeneratorError as exc:
        raise PipelineError(str(exc), "Voice Generation") from exc


def _phase_captions() -> None:
    from caption_generator import (
        AudioNotFoundError,
        CaptionGenerationError,
        CaptionGenerator,
        CaptionGeneratorError,
        FFmpegNotFoundError,
        WhisperModelLoadError,
        WhisperPackageNotFoundError,
    )

    caption_generator = CaptionGenerator()
    try:
        caption_generator.generate()
    except AudioNotFoundError as exc:
        raise PipelineError(str(exc), "Caption Generation") from exc
    except FFmpegNotFoundError as exc:
        raise PipelineError(str(exc), "Caption Generation") from exc
    except WhisperPackageNotFoundError as exc:
        raise PipelineError(str(exc), "Caption Generation") from exc
    except WhisperModelLoadError as exc:
        raise PipelineError(str(exc), "Caption Generation") from exc
    except CaptionGenerationError as exc:
        raise PipelineError(str(exc), "Caption Generation") from exc
    except CaptionGeneratorError as exc:
        raise PipelineError(str(exc), "Caption Generation") from exc


def _phase_scenes() -> None:
    from agents.scene_agent import (
        SceneAgent,
        SceneAgentError,
        SceneGenerationError,
        SceneOllamaConnectionError,
        SceneOllamaModelError,
        SceneValidationError,
        ScriptNotFoundError as SceneScriptNotFoundError,
    )

    scene_agent = SceneAgent()
    try:
        scene_agent.generate()
    except SceneScriptNotFoundError as exc:
        raise PipelineError(str(exc), "Scene Generation") from exc
    except SceneOllamaConnectionError as exc:
        raise PipelineError(str(exc), "Scene Generation") from exc
    except SceneOllamaModelError as exc:
        raise PipelineError(str(exc), "Scene Generation") from exc
    except SceneValidationError as exc:
        raise PipelineError(str(exc), "Scene Generation") from exc
    except SceneGenerationError as exc:
        raise PipelineError(str(exc), "Scene Generation") from exc
    except SceneAgentError as exc:
        raise PipelineError(str(exc), "Scene Generation") from exc


def _phase_visual_timeline() -> None:
    from agents.visual_asset_agent import APIKeyMissingError
    from agents.visual_timeline_agent import (
        CaptionsNotFoundError as TimelineCaptionsNotFoundError,
        FFmpegNotFoundError as TimelineFFmpegNotFoundError,
        NarrationNotFoundError,
        ScenesNotFoundError as TimelineScenesNotFoundError,
        TimelineAssetError,
        TimelineRenderError,
        VisualTimelineAgent,
        VisualTimelineAgentError,
    )

    visual_timeline_agent = VisualTimelineAgent()
    try:
        visual_timeline_agent.generate()
    except TimelineScenesNotFoundError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except APIKeyMissingError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except NarrationNotFoundError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except TimelineCaptionsNotFoundError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except TimelineFFmpegNotFoundError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except TimelineAssetError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except TimelineRenderError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc
    except VisualTimelineAgentError as exc:
        raise PipelineError(str(exc), "Visual Timeline") from exc


def _phase_thumbnail() -> None:
    from agents.thumbnail_agent import (
        FFmpegNotFoundError as ThumbnailFFmpegNotFoundError,
        ThumbnailAgent,
        ThumbnailAgentError,
        ThumbnailRenderError,
        TitleNotFoundError,
        VisualSourceNotFoundError,
    )

    thumbnail_agent = ThumbnailAgent()
    try:
        thumbnail_agent.generate()
    except TitleNotFoundError as exc:
        raise PipelineError(str(exc), "Thumbnail Generation") from exc
    except VisualSourceNotFoundError as exc:
        raise PipelineError(str(exc), "Thumbnail Generation") from exc
    except ThumbnailFFmpegNotFoundError as exc:
        raise PipelineError(str(exc), "Thumbnail Generation") from exc
    except ThumbnailRenderError as exc:
        raise PipelineError(str(exc), "Thumbnail Generation") from exc
    except ThumbnailAgentError as exc:
        raise PipelineError(str(exc), "Thumbnail Generation") from exc


def _read_script() -> str:
    path = ROOT_DIR / "scripts" / "script.txt"
    if not path.is_file():
        raise PipelineError("Script file was not created.", "Script Generation")
    return path.read_text(encoding="utf-8")


def pipeline_worker(job_id: str, job_manager: JobManager) -> None:
    """Entry point for the background worker."""
    try:
        run_job(job_id, job_manager)
    except PipelineError as exc:
        job_manager.fail(job_id, str(exc), phase=exc.phase)
        logger.error(
            "Job failed",
            extra={
                "job_id": job_id,
                "event": "job_failed",
                "phase": exc.phase,
                "error": str(exc),
            },
        )
