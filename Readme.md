# YT-Agent

**AI YouTube Agent** — A local-first pipeline that turns a topic into a finished YouTube Short, with automation-ready architecture for visuals, thumbnails, and upload.

---

## Project Vision

Build a fully autonomous AI-powered YouTube Shorts agent that can:

- Generate topics
- Write scripts
- Generate voiceovers
- Generate captions
- Generate visuals automatically
- Generate videos automatically
- Generate thumbnails
- Upload to YouTube
- Run on a schedule

The system runs on local hardware wherever possible and uses free or self-hosted tools.

---

## Progress

| Component | Status |
|-----------|--------|
| Script Generation | ✅ Complete |
| Metadata Generation | ✅ Complete |
| Voice Generation | ✅ Complete |
| Caption Generation | ✅ Complete |
| Video Generation | ✅ Complete |
| Visual Asset Agent | ⬜ Planned |
| Thumbnail Generation | ⬜ Planned |
| YouTube Upload | ⬜ Planned |
| Automation | ⬜ Planned |

**Phases complete:** 1, 2, 3, 4  
**Current focus:** Phase 4.5 — Visual Asset Agent (roadmap)

---

## Current Pipeline

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
```

Run the full pipeline (Phases 1–4):

```bash
pip install -r requirements.txt
python main.py "your topic here"
```

---

## Current Output Files

| File | Description |
|------|-------------|
| `scripts/script.txt` | Formatted narration script |
| `scripts/output.txt` | Raw script (debug) |
| `scripts/title.txt` | YouTube title |
| `scripts/description.txt` | Video description |
| `scripts/hashtags.txt` | Hashtags (one per line) |
| `audio/output.wav` | Narration audio |
| `captions/output.srt` | Burned-in-ready subtitles |
| `videos/output.mp4` | Final vertical Short (1080×1920) |

---

## Technology Stack

| Layer | Tools |
|-------|--------|
| **AI** | Ollama, Llama 3 |
| **Language** | Python 3.13 |
| **Voice** | Piper TTS |
| **Captions** | OpenAI Whisper (local, `base.en`) |
| **Video** | FFmpeg |
| **Future thumbnails** | Pillow (planned) |
| **Future upload** | YouTube Data API v3 (planned) |

---

## Project Structure

Only directories and modules that exist in the repository today:

```text
YT-agent/
├── assets/
│   └── backgrounds/
│       └── background.mp4      # background clip (or auto-generated placeholder)
├── audio/
│   └── output.wav              # generated narration
├── captions/
│   └── output.srt              # generated subtitles
├── scripts/
│   ├── script.txt
│   ├── output.txt
│   ├── title.txt
│   ├── description.txt
│   └── hashtags.txt
├── videos/
│   └── output.mp4              # final Short
├── models/
│   └── piper/                  # Piper voice model files
├── main.py                     # CLI entry point
├── script_generator.py         # Phase 1 — script
├── metadata_generator.py       # Phase 1 — metadata
├── voice_generator.py          # Phase 2 — voice
├── caption_generator.py        # Phase 3 — captions
├── video_generator.py          # Phase 4 — video
├── requirements.txt
└── Readme.md
```

---

## Completed Phases

### Phase 1 — Script Generation ✅

- Accepts a topic from the CLI or an interactive prompt
- Generates a YouTube Shorts script with Ollama (Llama 3)
- Target length: 140–180 words (validated: 120–200, with auto-retry)
- Produces title, description, and 10 hashtags from the script
- Enforces style rules (no narrator labels, scene directions, or host references)

**Modules:** `script_generator.py`, `metadata_generator.py`

---

### Phase 2 — Voice Generation ✅

- Reads `scripts/script.txt`
- Synthesizes narration with Piper TTS (`en_US-ryan-high`)
- Configurable speech rate (`length_scale` 1.25)
- Dynamic Piper timeout based on script word count
- Writes `audio/output.wav`

**Module:** `voice_generator.py`

---

### Phase 3 — Caption Generation ✅

- Transcribes `audio/output.wav` with local OpenAI Whisper (`base.en`)
- Verifies FFmpeg on PATH (audio decoding + later video phases)
- Writes `captions/output.srt`

**Module:** `caption_generator.py`

---

### Phase 4 — Basic Video Generation ✅

- Combines background video, narration, and burned-in subtitles
- Vertical output: **1080×1920**, **30 fps**, **H.264** + **AAC**
- Loops background when shorter than narration; trims to audio length
- Subtitle style: white text, black outline, bottom-center
- Writes `videos/output.mp4`

**Inputs:** `audio/output.wav`, `captions/output.srt`, `assets/backgrounds/background.mp4`  
**Module:** `video_generator.py`

---

## Future Roadmap

### Phase 4.5 — Visual Asset Agent (planned)

**Goal:** Remove dependency on manually provided background videos.

**Planned workflow:**

```text
Topic
  ↓
Script
  ↓
Voice
  ↓
Captions
  ↓
Scene Agent
  ↓
Image Agent
  ↓
Motion Effects
  ↓
Video
  ↓
Thumbnail
  ↓
Upload
  ↓
Automation
```

#### Scene Agent

- Reads the generated script
- Splits the script into multiple scenes
- Generates scene descriptions

#### Image Agent

- Generates images for each scene automatically

#### Motion Effects

- Apply zoom
- Apply pan
- Apply Ken Burns effect

#### Video Agent

- Assemble generated images
- Add narration
- Add subtitles
- Export final MP4

**Advantages:**

- Fully automated visuals
- No manual background video required
- Better topic relevance
- More scalable pipeline
- Closer to professional AI content workflows

---

### Phase 5 — Thumbnail Generation

- Generate an eye-catching thumbnail from topic and script
- YouTube-ready image output

---

### Phase 6 — YouTube Upload Automation

- Authenticate with YouTube Data API v3
- Upload video, thumbnail, title, description, and hashtags

---

### Phase 7 — Scheduling and Full Automation

- End-to-end scheduled runs
- Logging, error handling, and retries

---

## Requirements

### Hardware (reference setup)

- 16 GB RAM
- Python 3.13
- Ollama with Llama 3
- FFmpeg on PATH
- Piper TTS (`piper.exe` + voice model under `models/piper/`)

### Install

```bash
pip install -r requirements.txt
```

### Optional: run a single phase

```python
from script_generator import ScriptGenerator
from metadata_generator import MetadataGenerator
from voice_generator import VoiceGenerator
from caption_generator import CaptionGenerator
from video_generator import VideoGenerator

# After prior outputs exist, run individually:
# ScriptGenerator().generate_and_save("your topic")
# MetadataGenerator().generate_and_save(script, topic)
# VoiceGenerator().generate()
# CaptionGenerator().generate()
# VideoGenerator().generate()
```

---

## Success Criteria

The project is complete when:

- A topic can be generated automatically
- Script, voice, captions, and video are produced without manual steps
- Thumbnails and YouTube upload run automatically
- The full workflow can run on a schedule with minimal human input

**Today:** Phases 1–4 deliver a watchable Short from a single topic via `python main.py`.

---

## License

Add your license here if publishing publicly on GitHub.
