# YT-Agent

**AI-Powered Content Creation Platform** — Turn ideas or your own scripts into finished vertical videos with voice, captions, stock visuals, thumbnails, and publish-ready metadata. Local-first, automation-ready, and built for Shorts, Reels, and social video.

---

## Product Vision

YT-Agent is no longer just a YouTube automation tool. It is a **content creation platform** with two ways to produce video:

1. **AI Mode** — Start from a topic; the system writes the script and runs the full pipeline.
2. **Custom Script Mode** — Start from your script; the system handles production from voice through thumbnail and metadata.

Both modes share the same core engines: voice, captions, scene planning, visual asset selection, video assembly, and thumbnail generation. The platform runs on local hardware wherever possible (Ollama, Piper, Whisper, FFmpeg) and uses stock APIs for visuals.

---

## Core Features

### 1. AI Topic to Video

```text
Topic
  ↓
Script
  ↓
Voice
  ↓
Captions
  ↓
Scenes
  ↓
Visual Assets
  ↓
Video
  ↓
Thumbnail
  ↓
Metadata
```

**Today:** Fully supported via `python main.py "your topic"`. Metadata (title, description, hashtags) is generated in Phase 1 immediately after the script.

---

### 2. Custom Script to Video

```text
User Script
  ↓
Voice
  ↓
Captions
  ↓
Scenes
  ↓
Visual Assets
  ↓
Video
  ↓
Thumbnail
  ↓
Metadata
```

**Today:** Supported by placing your script in `scripts/script.txt`, then running pipeline phases from voice onward (see [Custom Script Mode](#custom-script-mode)). A dedicated CLI entry point for Custom Script Mode is on the roadmap.

---

## Progress Tracker

### Completed features

| Feature | Status |
|---------|--------|
| Script Generation | ✅ |
| Metadata Generation | ✅ |
| Voice Generation | ✅ |
| Caption Generation | ✅ |
| Scene Agent | ✅ |
| Visual Timeline Agent | ✅ |
| Final Video Generation | ✅ |
| Thumbnail Generation | ✅ |

### Core components (shipped)

| Component | Module |
|-----------|--------|
| Script Generation | `script_generator.py` |
| Metadata Generation | `metadata_generator.py` |
| Voice Generation | `voice_generator.py` |
| Caption Generation | `caption_generator.py` |
| Scene Agent | `agents/scene_agent.py` |
| Visual Timeline Agent | `agents/visual_timeline_agent.py` |
| Final Video Generation | `agents/visual_timeline_agent.py` (+ legacy `video_generator.py`) |
| Thumbnail Generation | `agents/thumbnail_agent.py` |

### Upcoming

| Phase | Name | Status |
|-------|------|--------|
| **6** | Background Music Agent | ⬜ Planned |
| **7** | YouTube Upload Agent | ⬜ Planned |
| **8** | Automation Agent | ⬜ Planned |
| — | Custom Script CLI mode | ⬜ Planned |
| — | AI image / video generation | ⬜ Planned |

### Visual asset sources

| Source | Status |
|--------|--------|
| Pexels Videos | ✅ Primary |
| Pexels Images | ✅ Fallback |
| Pixabay Images | ✅ Final fallback |
| AI Generation | ⬜ Planned |

---

## Product Scope

### AI Mode

```text
Topic
  ↓
Script Generation
  ↓
Voice Generation
  ↓
Caption Generation
  ↓
Scene Planning
  ↓
Visual Asset Selection
  ↓
Video Generation
  ↓
Thumbnail Generation
  ↓
Metadata Generation
```

**CLI:** `python main.py "your topic"`

---

### Custom Script Mode

```text
User Script
  ↓
Voice Generation
  ↓
Caption Generation
  ↓
Scene Planning
  ↓
Visual Asset Selection
  ↓
Video Generation
  ↓
Thumbnail Generation
  ↓
Metadata Generation
```

#### Custom Script Mode

1. Write your narration into `scripts/script.txt` (plain text, no scene directions).
2. Run phases individually:

```python
from metadata_generator import MetadataGenerator
from voice_generator import VoiceGenerator
from caption_generator import CaptionGenerator
from agents.scene_agent import SceneAgent
from agents.visual_timeline_agent import VisualTimelineAgent
from agents.thumbnail_agent import ThumbnailAgent

script = open("scripts/script.txt", encoding="utf-8").read()
topic = "your video topic or niche label"

VoiceGenerator().generate()
CaptionGenerator().generate()
SceneAgent().generate()
VisualTimelineAgent().generate()
ThumbnailAgent().generate()
MetadataGenerator().generate_and_save(script, topic)
```

---

## Visual pipeline

The **Visual Timeline Agent** uses a video-first timeline:

```text
1. Pexels Videos      ← primary
2. Pexels Images      ← fallback (Ken Burns / zoom / pan)
3. Pixabay Images     ← final fallback
        ↓
Timeline Builder (FFmpeg)
        ↓
videos/output.mp4
```

- Input: `scenes/scenes.json` (durations, titles, visual descriptions)
- Output: **1080×1920** vertical Short with narration and burned-in captions
- One final MP4 — no per-scene exports in `videos/`

---

## Technology Stack

| Layer | Tools |
|-------|--------|
| **AI** | Ollama, Llama 3 |
| **Language** | Python 3.13 |
| **Voice** | Piper TTS |
| **Captions** | OpenAI Whisper (local, `base.en`) |
| **Visual assets** | Pexels API (photos + videos), Pixabay API |
| **Video** | FFmpeg, ffprobe |
| **Thumbnails** | Pillow |
| **Future upload** | YouTube Data API v3 (planned) |

---

## Outputs

| Path | Description |
|------|-------------|
| `scripts/script.txt` | Narration script |
| `scripts/title.txt` | Video title |
| `scripts/description.txt` | Video description |
| `scripts/hashtags.txt` | Hashtags (one per line) |
| `audio/output.wav` | Narration audio |
| `captions/output.srt` | Shorts-style subtitles |
| `scenes/scenes.json` | Scene plan |
| `assets/timeline/` | Cached stock clips / images |
| `assets/cache/` | API search cache (24h) |
| `videos/output.mp4` | Final video (1080×1920) |
| `thumbnails/output.png` | Thumbnail (1280×720) |

---

## Project Structure

```text
YT-agent/
├── agents/
│   ├── scene_agent.py
│   ├── visual_timeline_agent.py
│   ├── thumbnail_agent.py
│   ├── subtitle_config.py
│   ├── visual_asset_agent.py       # legacy image-only path
│   └── timeline_video_builder.py   # legacy slideshow path
├── assets/
│   ├── backgrounds/
│   ├── cache/
│   ├── clips/
│   ├── scenes/
│   └── timeline/
├── audio/
├── captions/
├── scenes/
├── scripts/
├── thumbnails/
├── videos/
├── models/piper/
├── main.py                         # AI Mode — full pipeline
├── script_generator.py
├── metadata_generator.py
├── voice_generator.py
├── caption_generator.py
├── video_generator.py              # legacy background video
└── Readme.md
```

---

## Quick Start

### Install

```bash
pip install -r requirements.txt
```

### Environment (`.env`)

```env
PEXELS_API_KEY=your_key
PIXABAY_API_KEY=your_key
```

Optional subtitle tuning:

```env
SUBTITLE_FONT_SIZE=13
SUBTITLE_MAX_LINES=2
SUBTITLE_BOTTOM_MARGIN=110
SUBTITLE_FONT_NAME=Poppins SemiBold
```

### AI Mode (recommended)

```bash
python main.py "Mastering capital expenditure for startups"
```

### Requirements

- Python 3.13
- Ollama with Llama 3 (`ollama pull llama3`)
- FFmpeg and ffprobe on PATH
- Piper TTS + voice model under `models/piper/`

---

## Long-Term Vision

```text
Topic or User Script
  ↓
Production pipeline (voice → video → thumbnail)
  ↓
Music Agent
  ↓
Upload Agent
  ↓
Automation Agent (scheduled runs)
```

**Platform goals:**

- One command from topic or script to publish-ready assets
- Category-based background music
- Automatic YouTube upload (video + thumbnail + metadata)
- Fully scheduled, hands-off content creation

---

## License

Add your license here if publishing publicly on GitHub.
