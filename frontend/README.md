# AutoShorts Frontend

Premium skeuomorphic / neumorphic UI for the AutoShorts desktop-style experience. UI-only — no backend or API calls.

## Stack

- React 19 + Vite 6
- Tailwind CSS 4
- Framer Motion
- Lucide React

## Design

- Monochrome palette (`#0a0a0a` → `#1a1a1a`)
- Depth via neumorphic shadows, glass panels, soft white glow
- VisionOS / premium DAW-inspired aesthetic

## Run

```bash
cd frontend
npm install
npm run dev
```

## Flow

1. **Splash** — AutoShorts, tagline, rotating loader, status lines, fade to app
2. **Home** — Topic Mode & Custom Script Mode (elevated neo cards)
3. **Processing** — Circular progress, glass terminal with typing animation
4. **Result** — Floating dashboard panels, download placeholders

## Structure

```text
src/
├── components/
│   ├── splash/SplashScreen.jsx
│   ├── layout/AppShell.jsx, PageTransition.jsx
│   └── ui/          NeoButton, NeoInput, NeoCard, GlassTerminal, etc.
├── pages/           Home, Processing, Result
├── hooks/           useTypingEffect
└── constants/       pipeline phases & placeholders
```
