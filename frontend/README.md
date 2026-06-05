# AutoShorts Frontend

Premium UI for AutoShorts, connected to the FastAPI backend.

## Stack

- React 19 + Vite 6
- Tailwind CSS 3
- Framer Motion
- Lucide React

## Configuration

Copy `.env.example` to `.env` if the API is not on the default host:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Run (full stack)

**Terminal 1 — API** (from project root):

```bash
python -m uvicorn backend.api:app --reload
```

**Terminal 2 — UI**:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

## Frontend ↔ Backend flow

1. **Topic Mode** — `POST /generate/topic` → `job_id` → `/processing`
2. **Custom Script** — sanitize script → `POST /generate/script` → `job_id` → `/processing`
3. **Processing** — poll `GET /progress/{job_id}` every 2s
4. **Result** — on `status: completed`, `GET /result/{job_id}` → video + metadata (title, description with hashtags)

State (`job_id`, progress, result, errors) lives in `GenerationContext` — no full page reload.

## Structure

```text
src/
├── context/GenerationContext.jsx
├── lib/api.js
├── utils/sanitizeScript.js
├── constants/phases.js
├── pages/           Home, Processing, Result
└── components/ui/
```
