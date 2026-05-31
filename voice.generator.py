"""Compatibility entry point — implementation lives in voice_generator.py."""

from voice_generator import (
    DEFAULT_PIPER_EXECUTABLE,
    OUTPUT_PATH,
    PIPER_EXECUTABLE,
    SCRIPT_PATH,
    VOICE_MODEL,
    resolve_piper_executable,
    PiperNotFoundError,
    ScriptNotFoundError,
    VoiceGenerationError,
    VoiceGenerator,
    VoiceGeneratorError,
    VoiceModelNotFoundError,
)

__all__ = [
    "DEFAULT_PIPER_EXECUTABLE",
    "OUTPUT_PATH",
    "PIPER_EXECUTABLE",
    "resolve_piper_executable",
    "SCRIPT_PATH",
    "VOICE_MODEL",
    "PiperNotFoundError",
    "ScriptNotFoundError",
    "VoiceGenerationError",
    "VoiceGenerator",
    "VoiceGeneratorError",
    "VoiceModelNotFoundError",
]
