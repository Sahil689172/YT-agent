# AutoShorts

**AI-powered Shorts studio** — Turn ideas or your own scripts into finished vertical videos with voice, captions, stock visuals, and publish-ready metadata. Local-first pipeline (Ollama, Piper, Whisper, FFmpeg) plus a premium React web UI for creation and progress tracking.

> Previously documented as *YT-Agent*; the product UI and repo folder use **AutoShorts**.

---

## Product Vision

AutoShorts is a **content creation platform** with two ways to produce video:

1. **AI Mode** — Start from a topic; the system writes the script and runs the full pipeline.
2. **Custom Script Mode** — Start from your script; the system handles production from voice through video and metadata.

Both modes share the same core engines: voice, captions, scene planning, visual asset selection, and video assembly. The platform runs on local hardware wherever possible (Ollama, Piper, Whisper, FFmpeg) and uses stock APIs for visuals.

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
Metadata
```

**Today:** Supported via the web UI (`/create` → Custom Script), `POST /generate/script`, or by placing your script in `scripts/script.txt` and running phases from voice onward (see [Custom Script Mode](#custom-script-mode)).

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

### Upcoming

| Phase | Name | Status |
|-------|------|--------|
| **6** | Background Music Agent | ⬜ Planned |
| **7** | YouTube Upload Agent | ⬜ Planned |
| **8** | Automation Agent | ⬜ Planned |
| — | Custom Script via API + UI | ✅ |
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

script = open("scripts/script.txt", encoding="utf-8").read()
topic = "your video topic or niche label"

VoiceGenerator().generate()
CaptionGenerator().generate()
SceneAgent().generate()
VisualTimelineAgent().generate()
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
| **Image verification** | Pillow |
| **API** | FastAPI, Uvicorn |
| **Frontend** | React 19, Vite, React Router, Tailwind CSS, Framer Motion, GSAP |
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
| `jobs/{job_id}/` | Per-run API artifacts (video, script, metadata, `performance.txt`) |

---

## Performance optimizations

AutoShorts is tuned for **faster runs without lowering output quality**.

### Pipeline profiling

Every phase records **START**, **END**, and **DURATION** (UTC timestamps). A compact summary is printed at the end, for example:

```text
Script Generation: 4.2 sec
Metadata Generation: 1.1 sec
Voice Generation: 18.4 sec
Caption Generation: 0.9 sec
Scene Agent: 2.3 sec
Asset Search: 14.2 sec
Video Rendering: 31.7 sec
TOTAL: 72.8 sec
```

Timings appear in the **CLI terminal**, **FastAPI JSON logs** (`PERF` lines), and the **frontend processing screen** (`/progress/{job_id}` → `phase_timings`).

### Optimization sprint (runtime targets)

| Phase | Target | Technique |
|-------|--------|-----------|
| Metadata | &lt; 15 sec | **One** Ollama call → `TITLE:` / `DESCRIPTION:` / `HASHTAGS:`; auto-merges 4+ description paragraphs to 2–3 |
| Scene Agent | &lt; 20 sec | **One** Ollama JSON call (max 2 retries), truncated script in prompt |
| Asset Search | &lt; 30 sec | Parallel per scene, early-exit (video first), 12 search / 10 download workers |
| Total | &lt; 180 sec | Parallel asset search + script-first captions |

Timings print at job start (optimization banner) and end (summary with OK/OVER vs targets).

### Parallel asset search

- **Visual timeline:** All scenes search in parallel; per scene, Pexels video is tried first, then Pexels image + Pixabay in parallel only if needed.
- **Downloads:** Scene asset downloads run in parallel (file + topic cache).

### Faster captions (script-first)

When `scripts/script.txt` exists after voice generation:

```text
Script → timed cues → SRT   (Whisper skipped)
```

Whisper runs only if the script is missing or `CAPTIONS_USE_WHISPER=1` is set. Same Shorts-style segmentation rules apply.

### Topic asset cache

Re-running the **same topic** reuses:

- Downloaded timeline scene files (`assets/cache/topics/{hash}/`)
- API search results (24h file cache under `assets/cache/`)

### FFmpeg efficiency

- Segment concat uses **stream copy** (`-c copy`) instead of re-encoding each join.
- Segment encodes use `libx264 -preset fast`.
- Final burn-in pass uses `-preset fast` (subtitles still require one encode).

### Environment toggles

| Variable | Effect |
|----------|--------|
| `CAPTIONS_USE_WHISPER=1` | Force Whisper even when script exists |
| `FFMPEG_EXECUTABLE` | Custom FFmpeg path |
| `ASSET_SEARCH_WORKERS` | Parallel scene search workers (default 12) |
| `ASSET_DOWNLOAD_WORKERS` | Parallel download workers (default 10) |

---

## Project Structure

```text
AutoShorts/
├── frontend/                       # React UI (landing, create, processing, result)
│   ├── src/pages/
│   │   ├── LandingPage.jsx         # Marketing home (/)
│   │   ├── HomePage.jsx            # Create studio (/create)
│   │   ├── ProcessingPage.jsx
│   │   └── ResultPage.jsx
│   └── src/components/
│       ├── landing/                # CrowdCanvas, GlassButton
│       └── create/                 # StudioBackground, StudioAgentVideo
├── backend/
│   ├── api.py
│   ├── job_manager.py
│   └── pipeline_runner.py
├── agents/
│   ├── scene_agent.py
│   ├── visual_timeline_agent.py
│   ├── subtitle_config.py
│   ├── visual_asset_agent.py       # legacy image-only path
│   ├── topic_cache.py              # per-topic asset reuse
│   └── timeline_video_builder.py   # legacy slideshow path
├── assets/
│   ├── backgrounds/
│   ├── cache/
│   │   └── topics/                 # topic-hash scene cache
│   ├── clips/
│   ├── scenes/
│   └── timeline/
├── audio/
├── captions/
├── scenes/
├── scripts/
├── videos/
├── models/piper/
├── main.py                         # AI Mode — full pipeline
├── pipeline_timing.py              # per-phase profiling + summary logs
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
Production pipeline (voice → video → metadata)
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
- Automatic YouTube upload (video + metadata)
- Fully scheduled, hands-off content creation

---

## Backend API Architecture

The FastAPI layer exposes the same pipeline as `main.py` without rewriting generators. Jobs run in a background worker; the pipeline uses shared output paths, so **one job runs at a time** (additional jobs are queued).

```text
frontend/
  └── React UI (polls API)

backend/
  ├── api.py              # FastAPI routes, CORS, request models
  ├── job_manager.py      # Job IDs, progress, results, artifact copy
  ├── pipeline_runner.py  # Orchestrates existing generators per phase
  └── logging_config.py   # JSON structured logs

Existing generators (unchanged):
  script_generator → metadata_generator → voice_generator →
  caption_generator → scene_agent → visual_timeline_agent
```

### Job lifecycle

```text
POST /generate/topic  or  /generate/script
        ↓
   { job_id, status: "started" }
        ↓
GET /progress/{job_id}  (poll while running)
        ↓
GET /result/{job_id}    (when status is completed)
```

Per-job artifacts are copied to `jobs/{job_id}/` (video, title, description, hashtags, script).

---

## Available Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | API health check |
| `POST` | `/generate/topic` | Full pipeline from topic → `{ job_id, status }` |
| `POST` | `/generate/script` | Pipeline from user script (skips script generation) |
| `GET` | `/progress/{job_id}` | Live phase, `completed` / `total`, status |
| `GET` | `/result/{job_id}` | Title, description, hashtags, file paths |

### Example requests

**Topic mode**

```bash
curl -X POST http://127.0.0.1:8000/generate/topic \
  -H "Content-Type: application/json" \
  -d "{\"topic\": \"What is EBITDA?\"}"
```

**Custom script**

```bash
curl -X POST http://127.0.0.1:8000/generate/script \
  -H "Content-Type: application/json" \
  -d "{\"script\": \"Your narration here...\", \"topic\": \"Finance Short\"}"
```

**Progress**

```bash
curl http://127.0.0.1:8000/progress/{job_id}
```

**Result** (when complete)

```bash
curl http://127.0.0.1:8000/result/{job_id}
```

Interactive API docs: `http://127.0.0.1:8000/docs`

---

## Local Development Instructions

### 1. Install Python dependencies

From the project root:

```bash
pip install -r requirements.txt
```

### 2. Environment

Ensure `.env` includes `PEXELS_API_KEY` and `PIXABAY_API_KEY` (required for visual timeline). Ollama, Piper, FFmpeg, and Whisper must be available as for CLI usage.

### 3. Start the API server

From the project root (not inside `backend/`):

```bash
python -m uvicorn backend.api:app --reload
```

On Windows, if `uvicorn` is not recognized as a command (pip installed it without adding Scripts to PATH), always use `python -m uvicorn` above, or double-click / run:

```bat
run_api.bat
```

Default URL: `http://127.0.0.1:8000`

### 4. Start the frontend (separate terminal)

```bash
cd frontend
npm install    # includes gsap for landing crowd animation
npm run dev
```

Default UI: `http://127.0.0.1:5173`

CORS is enabled for `http://localhost:5173` and `http://127.0.0.1:5173`.

### 5. Frontend integration flow

1. Open `http://127.0.0.1:5173` → landing; click **Get Started** → `/create`
2. Choose **Topic Mode** or **Custom Script**, submit → `POST /generate/topic` or `/generate/script` → store `job_id`
3. Navigate to `/processing`; poll `GET /progress/{job_id}` every few seconds
4. When `status` is `completed`, load `GET /result/{job_id}` on `/result`
5. Use returned `video_path`, metadata, and performance fields in the UI

### Frontend dependencies

| Package | Use |
|---------|-----|
| `framer-motion` | Page transitions, form reveals, button hover |
| `gsap` | Landing page crowd canvas animation |
| `lucide-react` | Icons |
| `react-router-dom` | `/`, `/create`, `/processing`, `/result` |

---

## Web UI (Frontend)

The React app is a **premium studio experience**, not a dashboard. Routes:

| Route | Page | Description |
|-------|------|-------------|
| `/` | **Landing** | White marketing home — hero, animated crowd, glass capability cards, pipeline, CTA |
| `/create` | **Create studio** | Dark full-screen studio — topic or custom script → generation |
| `/processing` | **Processing** | Live phase progress + performance timings |
| `/result` | **Result** | Video, metadata, download/copy |

### Landing page (`/`)

- **Hero:** Headline, CTAs (Get Started → `/create`, Watch Demo), compact layout so the crowd is visible without scrolling.
- **Crowd animation:** Open Peeps sprite sheet + GSAP (`CrowdCanvas`) — dense walking crowd in the lower viewport, layered depth, smooth motion.
- **Capabilities:** Six features in **glassmorphism** cards (frosted blur, light borders).
- **Pipeline:** Animated workflow steps (topic → voice → captions → scenes → visuals → video).
- **Theme:** White background, black typography (Inter).

### Create page (`/create`)

Inspired by high-end agency landings (e.g. Mainframe-style interaction), adapted for AutoShorts:

- **Theme:** `#050505` cinematic dark — subtle grid, gradients, floating particles, light beams.
- **Nav:** AutoShorts logo + **Back to Home** pill.
- **Typewriter intro:** Sequential lines with blinking cursor before mode selection.
- **Mode pills:** **Topic Mode** or **Custom Script** — selected form animates in (Framer Motion).
- **Studio agent (desktop):** Mouse-scrub video on the right — head pose follows cursor via spring-smoothed frame mapping + seek queue (`StudioAgentVideo`).
- **Inputs:** Glassmorphism topic field / script textarea; premium **Generate** button (glow + lift on hover).
- **Script sanitization:** Strips `Narrator:`, `Voiceover:`, `Scene N:`, `Here's your script:` before API submit (`sanitizeScript.js`).

### Processing & result

- Dark neumorphic UI (existing `AppShell` on `/processing` and `/result`).
- Processing shows **phase timings** and optimization summary when the API provides `phase_timings` / `performance_summary`.

---

## Frontend ↔ Backend Architecture

The React app (`frontend/`) talks to the FastAPI server over HTTP. No terminal is required for end users.

```text
┌─────────────────┐     POST /generate/topic|script      ┌──────────────────┐
│  /create        │ ───────────────────────────────────► │  FastAPI         │
│  Topic / Script │ ◄──────────── job_id ──────────────── │  backend/api.py  │
└────────┬────────┘                                        └────────┬─────────┘
         │                                                           │
         ▼                                                           ▼
┌─────────────────┐     GET /progress/{id} (poll)        ┌──────────────────┐
│  /processing    │ ◄────────────────────────────────────── │  Job manager +   │
│  Live progress  │                                        │  pipeline_runner │
└────────┬────────┘                                        └────────┬─────────┘
         │ status = completed                                        │
         ▼                                                           ▼
┌─────────────────┐     GET /result/{id}                 jobs/{id}/output.mp4
│  /result        │ ◄── video, metadata ─── scripts/
└─────────────────┘
```

### Topic Mode

On `/create`, user picks **Topic Mode**, enters a Shorts topic (e.g. `What is EBITDA?`), and clicks **Generate**. The frontend calls `POST /generate/topic`. The backend runs the full pipeline: script → metadata → voice → captions → scenes → visual timeline → finalization.

### Custom Script Mode

User picks **Custom Script**, pastes plain narration (80–120 words recommended). The UI **sanitizes** prefixes (`Narrator:`, `Voiceover:`, scene labels, etc.) then calls `POST /generate/script`, which skips AI script generation and runs the rest of the pipeline.

### Generation flow (no page refresh)

| Step | Frontend | Backend |
|------|----------|---------|
| Start | Store `job_id` in React context | Queue job, run pipeline in worker |
| Progress | Poll `/progress/{job_id}` | Update `current_phase`, `completed` / `total` |
| Done | Auto-navigate to Results | Copy artifacts to `jobs/{job_id}/` |
| Display | Video via `/jobs/...` URLs | Static mount serves job files |

### Error handling (UI)

Friendly messages for: **Backend Offline**, **Network Error**, **Invalid Script**, **Generation Failed**, **Video Creation Failed**.

### Environment

Frontend: `frontend/.env` → `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`)

---

## License

Add your license here if publishing publicly on GitHub.
