"""CLI entry point for YouTube Shorts Phase 1–4.5A: script through scene agent."""

import logging
import sys

from agents.scene_agent import (
    SceneAgent,
    SceneAgentError,
    SceneGenerationError,
    SceneOllamaConnectionError,
    SceneOllamaModelError,
    SceneValidationError,
    ScriptNotFoundError as SceneScriptNotFoundError,
)
from caption_generator import (
    AudioNotFoundError,
    CaptionGenerationError,
    CaptionGenerator,
    CaptionGeneratorError,
    FFmpegNotFoundError,
    WhisperModelLoadError,
    WhisperPackageNotFoundError,
)
from metadata_generator import (
    MetadataGenerator,
    MetadataGeneratorError,
    MetadataOllamaConnectionError,
    MetadataOllamaModelError,
    MetadataValidationError,
)
from script_generator import (
    MAX_WORDS,
    MIN_WORDS,
    TARGET_MAX_WORDS,
    TARGET_MIN_WORDS,
    OllamaConnectionError,
    OllamaModelError,
    ScriptGenerator,
    ScriptGeneratorError,
    ScriptValidationError,
)
from video_generator import (
    AssetNotFoundError,
    BackgroundNotFoundError,
    FFmpegNotFoundError as VideoFFmpegNotFoundError,
    VideoGenerationError,
    VideoGenerator,
    VideoGeneratorError,
)
from voice_generator import (
    PiperNotFoundError,
    ScriptNotFoundError,
    VoiceGenerationError,
    VoiceGenerator,
    VoiceGeneratorError,
    VoiceModelNotFoundError,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def read_topic() -> str:
    """Read topic from command-line args or interactive prompt."""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:]).strip()
    try:
        return input("Enter YouTube Shorts topic: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)


def main() -> int:
    topic = read_topic()
    if not topic:
        print("Error: Topic cannot be empty.", file=sys.stderr)
        return 1

    script_generator = ScriptGenerator()
    metadata_generator = MetadataGenerator()
    voice_generator = VoiceGenerator()
    caption_generator = CaptionGenerator()
    video_generator = VideoGenerator()
    scene_agent = SceneAgent()

    try:
        logger.info("Phase 1: generating script")
        script, raw_path, formatted_path = script_generator.generate_and_save(topic)
    except OllamaConnectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OllamaModelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ScriptValidationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ScriptGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    word_count = len(script.split())
    if TARGET_MIN_WORDS <= word_count <= TARGET_MAX_WORDS:
        range_note = f"target {TARGET_MIN_WORDS}-{TARGET_MAX_WORDS}"
    elif MIN_WORDS <= word_count <= MAX_WORDS:
        range_note = f"valid {MIN_WORDS}-{MAX_WORDS}"
    else:
        range_note = f"outside {MIN_WORDS}-{MAX_WORDS}"
    print(f"Script saved — final word count: {word_count} ({range_note})")
    print(f"  Readable: {formatted_path}")
    print(f"  Debug:    {raw_path}")

    try:
        logger.info("Phase 1: generating metadata")
        metadata, title_path, description_path, hashtags_path = (
            metadata_generator.generate_and_save(script, topic)
        )
    except MetadataOllamaConnectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except MetadataOllamaModelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except MetadataValidationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Tip: Try running again; model output can vary.", file=sys.stderr)
        return 1
    except MetadataGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Metadata saved")
    print(f"  Title:       {title_path}")
    print(f"  Description: {description_path}")
    print(f"  Hashtags:    {hashtags_path}")
    print(f"  Title preview: {metadata.title}")

    try:
        logger.info("Phase 2: generating voice narration")
        print("\nPhase 2 — Voice generation")
        audio_path = voice_generator.generate()
    except PiperNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except VoiceModelNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ScriptNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except VoiceGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except VoiceGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\nVoice saved -> {audio_path}")

    try:
        logger.info("Phase 3: generating captions")
        print("\nPhase 3 — Caption generation")
        srt_path = caption_generator.generate()
    except AudioNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except FFmpegNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except WhisperPackageNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except WhisperModelLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except CaptionGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except CaptionGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\nCaptions saved -> {srt_path}")

    try:
        logger.info("Phase 4: generating video")
        print("\nPhase 4 — Video generation")
        video_path = video_generator.generate()
    except AssetNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except BackgroundNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except VideoFFmpegNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except VideoGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except VideoGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\nVideo saved -> {video_path}")

    try:
        logger.info("Phase 4.5A: generating visual scenes")
        print("\nPhase 4.5A — Scene Agent")
        _, scenes_path = scene_agent.generate()
    except SceneScriptNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except SceneOllamaConnectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except SceneOllamaModelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except SceneValidationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Tip: Try running again; model output can vary.", file=sys.stderr)
        return 1
    except SceneGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except SceneAgentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\nScenes saved -> {scenes_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
