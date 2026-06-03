# YT-Agent

**AI YouTube Agent** — A local-first pipeline that turns a topic into a finished YouTube Short, with a video-first visual timeline and a clear roadmap toward music, thumbnails, upload, and full automation.

---

## Project Vision

Build a fully autonomous AI-powered YouTube Shorts agent that can:

- Generate topics
- Write scripts and metadata
- Generate voiceovers and captions
- Source stock video and images automatically
- Assemble a single polished vertical video
- Add background music, thumbnails, and YouTube upload
- Run on a schedule with minimal human input

The system runs on local hardware wherever possible and uses free or self-hosted tools.

---

## Progress Tracker

### Completed

| Phase | Name | Status |
|-------|------|--------|
| **1** | Script Generation | ✅ Complete |
| **1** | Metadata Generation (title, description, hashtags) | ✅ Complete |
| **2** | Voice Generation | ✅ Complete |
| **3** | Caption Generation | ✅ Complete |
| **4** | Video Generation (legacy background mode) | ✅ Complete |
| **4.5A** | Scene Agent | ✅ Complete |
| **4.5B** | Visual Timeline Agent (video-first pipeline) | ✅ Complete |

The current default pipeline uses **Phase 4.5** (Scene Agent + Visual Timeline Agent). Phase 4 (`video_generator.py`) remains available as a legacy path that loops a manual background clip.

### Upcoming

| Phase | Name | Status |
|-------|------|--------|
| **5** | Background Music Agent | ⬜ Planned |
| **6** | Thumbnail Agent | ⬜ Planned |
| **7** | YouTube Upload Agent | ⬜ Planned |
| **8** | Automation Agent | ⬜ Planned |

### Future visual sources

| Source | Status |
|--------|--------|
| Pexels Videos | ✅ Integrated (primary) |
| Pexels Images | ✅ Integrated (fallback) |
| Pixabay Images | ✅ Integrated (final fallback) |
| AI Image / Video Generation | ⬜ Planned |

---

## Current Pipeline

```text
Topic
  ↓
Script (+ metadata)
  ↓
Voice
  ↓
Captions
  ↓
Scene Agent
  ↓
Visual Timeline Agent
  ↓
Final Video
```

### Visual Timeline Agent (search order)

```text
1. Pexels Videos      ← primary (real stock clips)
2. Pexels Images      ← fallback (motion effects applied)
3. Pixabay Images     ← final fallback
4. AI Generation      ← future roadmap
        ↓
Timeline Builder (FFmpeg)
        ↓
videos/output.mp4
```

- Reads `scenes/scenes.json` (per-scene duration, title, visual description)
- Normalizes segment lengths to narration duration
- Trims stock video or applies Ken Burns / zoom / pan on images
- Muxes `audio/output.wav` and burns in `captions/output.srt`
- Produces **one** final file — no per-scene `scene_1.mp4` exports in `videos/`

### Run the full pipeline

```bash
pip install -r requirements.txt
python main.py "your topic here"
```

**Environment:** create a `.env` file with at least `PEXELS_API_KEY` (recommended). Optional: `PIXABAY_API_KEY` for image fallback when Pexels has no match.

---

## Technology Stack

| Layer | Tools |
|-------|--------|
| **AI** | Ollama, Llama 3 |
| **Language** | Python 3.13 |
| **Voice** | Piper TTS |
| **Captions** | OpenAI Whisper (local, `base.en`) |
| **Visual assets** | Pexels API (photos + videos), Pixabay API |
| **Video processing** | FFmpeg, ffprobe |
| **Image handling** | Pillow |
| **Future thumbnails** | Pillow (planned) |
| **Future upload** | YouTube Data API v3 (planned) |

---

## Current Output

| Path | Description |
|------|-------------|
| `scripts/script.txt` | Formatted narration script |
| `scripts/output.txt` | Raw script (debug) |
| `scripts/title.txt` | YouTube title |
| `scripts/description.txt` | Video description |
| `scripts/hashtags.txt` | Hashtags (one per line) |
| `audio/output.wav` | Narration audio |
| `captions/output.srt` | Burned-in-ready subtitles |
| `scenes/scenes.json` | Scene list from Scene Agent |
| `assets/timeline/` | Cached stock clips/images per scene |
| `assets/cache/` | 24h API search cache |
| `videos/output.mp4` | Final vertical Short (1080×1920, 30 fps) |

---

## Project Structure

```text
YT-agent/
├── agents/
│   ├── scene_agent.py              # Phase 4.5A — script → scenes.json
│   ├── visual_timeline_agent.py    # Phase 4.5B — video-first timeline + final MP4
│   ├── visual_asset_agent.py       # Legacy — image download only (fallback tooling)
│   └── timeline_video_builder.py   # Legacy — image slideshow + motion (fallback tooling)
├── assets/
│   ├── backgrounds/                # Legacy Phase 4 background clip
│   ├── cache/                      # Pexels / Pixabay / video search cache
│   ├── scenes/                     # Legacy downloaded stills (image-only path)
│   └── timeline/                   # Cached scene_N.mp4 / scene_N.jpg + manifest.json
├── audio/
│   └── output.wav
├── captions/
│   └── output.srt
├── scenes/
│   └── scenes.json
├── scripts/
│   ├── script.txt
│   ├── output.txt
│   ├── title.txt
│   ├── description.txt
│   └── hashtags.txt
├── videos/
│   └── output.mp4
├── models/
│   └── piper/                      # Piper voice model
├── main.py                         # CLI — Phases 1 → 4.5B
├── script_generator.py             # Phase 1 — script
├── metadata_generator.py           # Phase 1 — metadata
├── voice_generator.py              # Phase 2 — voice
├── caption_generator.py            # Phase 3 — captions
├── video_generator.py              # Phase 4 — legacy background video
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
- Writes `audio/output.wav`

**Module:** `voice_generator.py`

---

### Phase 3 — Caption Generation ✅

- Transcribes `audio/output.wav` with local OpenAI Whisper (`base.en`)
- Writes `captions/output.srt`

**Module:** `caption_generator.py`

---

### Phase 4 — Basic Video Generation ✅ (legacy)

- Combines a looping background clip, narration, and burned-in subtitles
- Vertical output: **1080×1920**, **30 fps**, **H.264** + **AAC**
- **Not used by default** in `main.py`; superseded by Phase 4.5 for automated visuals

**Module:** `video_generator.py`

---

### Phase 4.5A — Scene Agent ✅

- Reads `scripts/script.txt`
- Uses narration duration (ffprobe on `audio/output.wav`) to size the timeline
- Splits the script into 6–15 scenes with `duration_seconds`, `title`, and `visual_description`
- Writes `scenes/scenes.json`

**Module:** `agents/scene_agent.py`

---

### Phase 4.5B — Visual Timeline Agent ✅

- Video-first stock search: **Pexels Videos → Pexels Images → Pixabay Images**
- Downloads assets on demand with search and file caching
- Builds one FFmpeg timeline (trim video clips or motion on stills)
- Adds narration and burned-in captions
- Exports `videos/output.mp4`

**Progress steps:** Reading scenes → Pexels Videos → Images → Building timeline → Motion/trim → Narration → Captions → Completed

**Module:** `agents/visual_timeline_agent.py`

**Legacy modules** (still in repo for image-only workflows): `visual_asset_agent.py`, `timeline_video_builder.py`

---

## Future Roadmap

### Phase 5 — Background Music Agent ⬜

**Goal:**

```text
Video + Narration + Category-Based Background Music
```

**Example categories:** Finance, Business, Technology, History, General

---

### Phase 6 — Thumbnail Agent ⬜

**Goal:** Generate an eye-catching thumbnail from topic and script.

**Output:** `thumbnails/output.png`

---

### Phase 7 — YouTube Upload Agent ⬜

**Goal:** Publish the Short without manual steps.

**Uploads:** video, thumbnail, title, description, hashtags

**API:** YouTube Data API v3

---

### Phase 8 — Automation Agent ⬜

**Goal:** Run the entire pipeline automatically on a schedule.

**Includes:** logging, error handling, retries, and hands-off topic → published Short flow

---

## Long-Term Vision

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
Visual Timeline Agent
  ↓
Music Agent
  ↓
Thumbnail Agent
  ↓
Upload Agent
  ↓
Automation Agent
```

---

## Requirements

### Hardware (reference setup)

- 16 GB RAM recommended
- Python 3.13
- Ollama with Llama 3
- FFmpeg and ffprobe on PATH
- Piper TTS (`piper.exe` + voice model under `models/piper/`)

### Install

```bash
pip install -r requirements.txt
```

### API keys (`.env`)

```env
PEXELS_API_KEY=your_key
PIXABAY_API_KEY=your_key
```

### Optional: run a single phase

```python
from script_generator import ScriptGenerator
from metadata_generator import MetadataGenerator
from voice_generator import VoiceGenerator
from caption_generator import CaptionGenerator
from agents.scene_agent import SceneAgent
from agents.visual_timeline_agent import VisualTimelineAgent

# After prior outputs exist:
# ScriptGenerator().generate_and_save("your topic")
# MetadataGenerator().generate_and_save(script, topic)
# VoiceGenerator().generate()
# CaptionGenerator().generate()
# SceneAgent().generate()
# VisualTimelineAgent().generate()
```

Legacy image-only path:

```python
from agents.visual_asset_agent import VisualAssetAgent
from agents.timeline_video_builder import TimelineVideoBuilder

# VisualAssetAgent().generate()
# TimelineVideoBuilder().generate()
```

---

## Success Criteria

The project is complete when:

- A topic can drive the full pipeline without manual asset gathering
- Script, voice, captions, video, music, thumbnail, and upload run automatically
- The workflow can run on a schedule with minimal human input

**Today:** Phases 1–3 and 4.5 deliver a watchable, stock-video-first Short from a single topic via `python main.py`.

---

## License

Add your license here if publishing publicly on GitHub.
