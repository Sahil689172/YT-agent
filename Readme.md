# AI YouTube Agent

## Project Goal

Build a fully automated AI-powered YouTube Shorts agent that can create and upload educational content with minimal human intervention.

The system will run completely on local hardware wherever possible and use free tools and services.

---

# Final Workflow

```text
Topic
  ↓
Script
  ↓
Voice
  ↓
Captions
  ↓
Video
  ↓
Thumbnail
  ↓
YouTube Upload
  ↓
Automation
```

This workflow is now locked and will remain the foundation of the project.

---

# Project Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Script + metadata generation | **Complete** |
| 2 | Voice generation (Piper TTS) | **Complete** |
| 3 | Caption generation (OpenAI Whisper) | **Complete** |
| 4 | Video generation | Not started |
| 5 | Thumbnail generation | Not started |
| 6 | YouTube upload | Not started |
| 7 | Automation | Not started |

**Current focus:** Phase 4 — Video Generation

### Run the pipeline (Phases 1–3)

```bash
pip install -r requirements.txt
python main.py "your topic here"
```

**Outputs:**

```text
scripts/script.txt          # formatted script
scripts/output.txt          # raw script (debug)
scripts/title.txt
scripts/description.txt
scripts/hashtags.txt
audio/output.wav
captions/output.srt
```

---

# Current Hardware

* RAM: 16 GB
* Python: 3.13
* Ollama: Installed
* Model: Llama 3
* FFmpeg: Installed (PATH)
* Piper TTS: `C:/Tools/piper/piper.exe`
* OpenAI Whisper: `base.en` (local, via Python package)

---

---

# Project Vision

The agent should eventually be capable of:

* Generating content ideas
* Writing scripts
* Creating voiceovers
* Generating subtitles
* Producing short-form videos
* Creating thumbnails
* Uploading to YouTube automatically
* Running on a schedule
* Operating with minimal human input

---

# Technology Stack

## AI

* Ollama
* Llama 3

## Backend

* Python 3.13

## Voice Generation

* Piper TTS

## Video Processing

* FFmpeg

## Captions

* OpenAI Whisper (local Python package, `base.en` model)
* FFmpeg (required on PATH for Whisper audio decoding and future video phases)

## Thumbnail Generation

* Pillow

## Upload System

* YouTube Data API v3

## Automation

* n8n (Future Phase)

---

# Development Phases

---

## Phase 1 — Script + Metadata Generation ✅ Complete

### Goal

Convert a topic into a YouTube Shorts script and upload metadata.

### Input

Topic

Example:

```text
What are stocks?
```

### Output

```text
scripts/output.txt          # raw script (debug)
scripts/script.txt          # formatted script (voice input)
scripts/title.txt
scripts/description.txt
scripts/hashtags.txt
```

### Responsibilities

* Accept topic input (CLI or prompt)
* Generate script (target 140–180 words, validated 120–200)
* Auto-retry if word count is out of range
* Generate title, description, and 10 hashtags from the script
* Remove narrator labels and scene directions
* Save all files under `scripts/`

### Module

`script_generator.py`, `metadata_generator.py`, `main.py`

### Deliverable

Working script and metadata pipeline using Ollama (Llama 3).

---

## Phase 2 — Voice Generation ✅ Complete

### Goal

Convert the formatted script into narration audio.

### Input

```text
scripts/script.txt
```

### Output

```text
audio/output.wav
```

### Responsibilities

* Verify Piper executable and voice model
* Read `scripts/script.txt`
* Generate narration with Piper (`en_US-ryan-high`, `length_scale` 1.25)
* Dynamic timeout based on script word count
* Save WAV file

### Module

`voice_generator.py`

### Deliverable

Natural-sounding local AI voice narration.

---

## Phase 3 — Caption Generation ✅ Complete

### Goal

Create subtitles from narration audio using local OpenAI Whisper.

### Input

```text
audio/output.wav
```

### Output

```text
captions/output.srt
```

### Process

```text
audio/output.wav
        ↓
OpenAI Whisper (local, base.en)
        ↓
captions/output.srt
```

### Responsibilities

* Verify narration audio exists
* Verify FFmpeg is available (used by Whisper for audio decoding; required for later phases)
* Load the `base.en` Whisper model locally
* Transcribe `audio/output.wav`
* Write a valid SRT file to `captions/output.srt`

### Setup

```bash
pip install -r requirements.txt
```

FFmpeg must be on your PATH. The first run downloads the `base.en` model automatically.

### Run (Phase 3 only)

After Phase 2 has produced `audio/output.wav`:

```python
from caption_generator import CaptionGenerator
CaptionGenerator().generate()
```

### Module

`caption_generator.py`

### Deliverable

Ready-to-use SRT captions synced to the narration audio.

---

## Phase 4 — Video Generation

### Goal

Generate a YouTube Shorts video.

### Inputs

```text
audio/output.wav
captions/output.srt
assets/background.mp4
```

### Output

```text
videos/output.mp4
```

### Responsibilities

* Create vertical video
* Add narration
* Add subtitles
* Add transitions
* Export final short

### Deliverable

Fully watchable short-form video.

---

## Phase 5 — Thumbnail Generation

### Goal

Create an eye-catching thumbnail.

### Input

Topic and script.

### Output

```text
thumbnails/output.png
```

### Responsibilities

* Generate bold text
* Generate attractive layout
* Create YouTube-ready image

### Deliverable

Professional thumbnail.

---

## Phase 6 — YouTube Upload

### Goal

Publish content automatically.

### Inputs

```text
videos/output.mp4
thumbnails/output.png
```

### Responsibilities

* Authenticate user
* Upload video
* Upload thumbnail
* Generate title
* Generate description
* Generate hashtags

### Deliverable

Video published on YouTube.

---

## Phase 7 — Automation

### Goal

Run the entire pipeline automatically.

### Workflow

```text
Topic
 ↓
Script
 ↓
Voice
 ↓
Captions
 ↓
Video
 ↓
Thumbnail
 ↓
Upload
```

### Responsibilities

* Daily execution
* Logging
* Error handling
* Retry failed tasks

### Deliverable

Fully autonomous content pipeline.

---

# Future Enhancements

## Multi-Agent Architecture

Agent 1:
Topic Research

Agent 2:
Script Writer

Agent 3:
SEO Optimizer

Agent 4:
Thumbnail Creator

Agent 5:
Uploader

---

# Success Criteria

The project is considered complete when:

* A topic is generated automatically
* A script is written automatically
* Voice narration is generated automatically
* Captions are generated automatically
* Video is generated automatically
* Thumbnail is generated automatically
* Video is uploaded automatically
* Entire workflow can run on schedule

without manual intervention.

---

# Current Focus

Phases **1–3** are complete and integrated in `main.py`:

```text
Topic → Script + Metadata → Voice → Captions
```

Next up: **Phase 4 — Video Generation** (`audio/output.wav` + `captions/output.srt` → `videos/output.mp4`).
