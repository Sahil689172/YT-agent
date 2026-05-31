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

# Current Hardware

* RAM: 16 GB
* Python: 3.13
* Ollama: Installed
* Model: Llama 3
* FFmpeg: Installed
* Cursor Pro: Available

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

* Auto-generated SRT files

## Thumbnail Generation

* Pillow

## Upload System

* YouTube Data API v3

## Automation

* n8n (Future Phase)

---

# Development Phases

---

## Phase 1 — Script Generation

### Goal

Convert a topic into a YouTube Shorts script.

### Input

Topic

Example:

```text
What are stocks?
```

### Output

```text
scripts/output.txt
```

### Responsibilities

* Accept topic input
* Generate 80–120 word script
* Remove narrator labels
* Remove scene directions
* Save script to file

### Deliverable

Working script generator using Ollama.

---

## Phase 2 — Voice Generation

### Goal

Convert script into narration.

### Input

```text
scripts/output.txt
```

### Output

```text
audio/output.wav
```

### Responsibilities

* Read generated script
* Generate voice narration
* Save WAV file

### Deliverable

Natural sounding AI voice.

---

## Phase 3 — Caption Generation

### Goal

Create subtitles from generated script.

### Input

```text
scripts/output.txt
```

### Output

```text
captions/output.srt
```

### Responsibilities

* Split script into subtitle blocks
* Generate timestamps
* Produce valid SRT file

### Deliverable

Ready-to-use captions.

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

We are currently working on:

## Phase 1 — Script Generation

Nothing else should be developed until Phase 1 is fully working and tested.
