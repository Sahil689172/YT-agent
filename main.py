"""CLI entry point for YouTube Shorts script generation."""

import sys

from script_generator import (
    OllamaConnectionError,
    OllamaModelError,
    ScriptGenerator,
    ScriptGeneratorError,
    ScriptValidationError,
)


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

    generator = ScriptGenerator()

    try:
        script, path = generator.generate_and_save(topic)
    except OllamaConnectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OllamaModelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ScriptValidationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Tip: Try running again; model output can vary.", file=sys.stderr)
        return 1
    except ScriptGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    word_count = len(script.split())
    print(f"Script saved ({word_count} words) -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
