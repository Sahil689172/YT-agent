import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader2, Sparkles } from 'lucide-react'
import CreateNav from '../components/create/CreateNav'
import StudioBackground from '../components/create/StudioBackground'
import StudioAgentVideo from '../components/create/StudioAgentVideo'
import ErrorBanner from '../components/ui/ErrorBanner'
import { useSequentialTypewriter } from '../hooks/useTypewriter'
import { sanitizeScript } from '../lib/sanitizeScript'
import { useGeneration } from '../context/GenerationContext'
import { ApiError } from '../lib/api'

const TYPEWRITER_LINES = [
  'Tell us what you want to create.',
  "We'll handle the script, visuals, voice, captions, and video.",
]

const TOPIC_PLACEHOLDERS = ['What is EBITDA?', 'Marketing Strategy', '5 Habits for Productivity']

const fade = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
}

function TypewriterBlock() {
  const { lines, done } = useSequentialTypewriter(TYPEWRITER_LINES, {
    speed: 36,
    startDelay: 500,
    linePause: 380,
  })

  return (
    <motion.div
      className="mb-8 sm:mb-10 min-h-[4.5rem] sm:min-h-[5.5rem]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6, delay: 0.15 }}
    >
      <p
        className="text-[clamp(17px,3.5vw,24px)] leading-[1.4] font-light text-white/75"
        style={{ fontWeight: 400 }}
      >
        {lines.map((line, i) => (
          <span key={i} className="block">
            {line}
            {i === lines.length - 1 && !done && (
              <span className="studio-cursor ml-0.5 inline-block" aria-hidden />
            )}
          </span>
        ))}
      </p>
    </motion.div>
  )
}

function ModePill({ active, onClick, children }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      className={`
        relative rounded-full px-8 py-3.5 text-[15px] sm:text-base font-medium tracking-tight
        transition-colors duration-300
        ${
          active
            ? 'bg-white text-[#050505] shadow-[0_0_40px_rgba(255,255,255,0.15)]'
            : 'border border-white/15 bg-white/[0.04] text-white/70 hover:border-white/25 hover:bg-white/[0.07] hover:text-white/90'
        }
      `}
      whileHover={{ y: active ? 0 : -2 }}
      whileTap={{ scale: 0.98 }}
      layout
    >
      {children}
      {active && (
        <motion.span
          layoutId="mode-glow"
          className="pointer-events-none absolute inset-0 rounded-full ring-1 ring-white/30"
          transition={{ type: 'spring', stiffness: 380, damping: 30 }}
        />
      )}
    </motion.button>
  )
}

function GenerateButton({ loading, disabled, onClick, label = 'Generate' }) {
  return (
    <motion.button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      className="studio-generate-btn group mt-8 inline-flex w-full items-center justify-center gap-2.5 rounded-full py-4 text-base font-semibold tracking-tight text-[#050505] disabled:opacity-40 disabled:pointer-events-none sm:w-auto sm:min-w-[220px] sm:px-12"
      whileHover={disabled ? {} : { y: -3, scale: 1.02 }}
      whileTap={disabled ? {} : { y: 0, scale: 0.99 }}
    >
      {loading ? (
        <>
          <Loader2 size={20} className="animate-spin" />
          Starting…
        </>
      ) : (
        <>
          <Sparkles size={18} className="opacity-80 transition-transform group-hover:rotate-12" />
          {label}
        </>
      )}
    </motion.button>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const { startTopic, startScript, loading, error, clearJob } = useGeneration()
  const [mode, setMode] = useState(null)
  const [topic, setTopic] = useState('')
  const [script, setScript] = useState('')
  const [localError, setLocalError] = useState(null)
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * TOPIC_PLACEHOLDERS.length))

  const displayError = localError || error

  async function handleTopicGenerate() {
    setLocalError(null)
    clearJob()
    try {
      await startTopic(topic.trim())
      navigate('/processing')
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setLocalError(
          new ApiError('Network Error', err?.message || 'Could not start generation.'),
        )
      }
    }
  }

  async function handleScriptGenerate() {
    setLocalError(null)
    clearJob()
    const cleaned = sanitizeScript(script)
    const topicLabel = topic.trim() || 'Custom Script'
    try {
      await startScript(cleaned, topicLabel)
      navigate('/processing')
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setLocalError(
          new ApiError('Network Error', err?.message || 'Could not start generation.'),
        )
      }
    }
  }

  return (
    <div className="studio-page relative h-screen min-h-[100dvh] w-full overflow-hidden bg-[#050505] text-white">
      <StudioBackground />
      <CreateNav />

      <div className="relative z-10 flex h-full min-h-[100dvh] items-center overflow-y-auto px-5 pb-8 pt-24 sm:px-8">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-10 lg:flex-row lg:items-center lg:gap-6 xl:gap-10">
          <div className="min-w-0 flex-1 lg:max-w-[52%]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
          >
            <h1 className="text-[clamp(2rem,5vw,3.25rem)] font-semibold leading-[1.08] tracking-tight text-white">
              Create Your Next Short
            </h1>
            <p className="mt-3 max-w-xl text-base font-light leading-relaxed text-white/45 sm:text-lg">
              Choose a topic or paste your own script. AutoShorts will generate a complete
              short-form video.
            </p>
          </motion.div>

          <TypewriterBlock />

          {displayError && (
            <div className="mb-6 max-w-xl">
              <ErrorBanner
                title={displayError.title}
                message={displayError.message}
                onDismiss={() => {
                  setLocalError(null)
                  clearJob()
                }}
              />
            </div>
          )}

          <motion.div
            className="mb-10 flex flex-wrap gap-3 sm:gap-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.4 }}
          >
            <ModePill active={mode === 'topic'} onClick={() => setMode('topic')}>
              Topic Mode
            </ModePill>
            <ModePill active={mode === 'script'} onClick={() => setMode('script')}>
              Custom Script
            </ModePill>
          </motion.div>

          <AnimatePresence mode="wait">
            {mode === 'topic' && (
              <motion.div
                key="topic"
                className="max-w-xl"
                initial={fade.initial}
                animate={fade.animate}
                exit={fade.exit}
                transition={fade.transition}
              >
                <label htmlFor="topic" className="sr-only">
                  Topic
                </label>
                <input
                  id="topic"
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  disabled={loading}
                  placeholder={TOPIC_PLACEHOLDERS[placeholderIdx]}
                  className="studio-input w-full rounded-2xl px-5 py-4 text-lg text-white placeholder:text-white/25 focus:outline-none disabled:opacity-50"
                  autoFocus
                />
                <GenerateButton
                  loading={loading}
                  disabled={!topic.trim()}
                  onClick={handleTopicGenerate}
                  label="Generate"
                />
              </motion.div>
            )}

            {mode === 'script' && (
              <motion.div
                key="script"
                className="max-w-2xl"
                initial={fade.initial}
                animate={fade.animate}
                exit={fade.exit}
                transition={fade.transition}
              >
                <label htmlFor="script" className="sr-only">
                  Script
                </label>
                <textarea
                  id="script"
                  value={script}
                  onChange={(e) => setScript(e.target.value)}
                  disabled={loading}
                  rows={8}
                  placeholder="Paste your narration script here..."
                  className="studio-input studio-textarea w-full resize-y rounded-2xl px-5 py-4 text-base leading-relaxed text-white placeholder:text-white/25 focus:outline-none disabled:opacity-50 min-h-[180px]"
                  autoFocus
                />
                <ul className="mt-4 space-y-1.5 text-sm text-white/40">
                  <li>
                    <span className="text-white/55">Recommended:</span> 80–120 words
                  </li>
                  <li>Designed for 30–45 second videos</li>
                  <li>Plain text only — no JSON required</li>
                </ul>
                <GenerateButton
                  loading={loading}
                  disabled={!script.trim()}
                  onClick={handleScriptGenerate}
                  label="Generate"
                />
              </motion.div>
            )}
          </AnimatePresence>
          </div>

          <motion.aside
            className="relative hidden min-h-[360px] flex-1 md:block md:min-h-[420px] lg:min-h-0 lg:h-[min(72vh,620px)]"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
          >
            <StudioAgentVideo className="h-full" />
            <p className="pointer-events-none absolute bottom-0 left-0 right-0 text-center text-[11px] tracking-wide text-white/25">
              Move your cursor — the studio agent looks your way
            </p>
          </motion.aside>
        </div>
      </div>
    </div>
  )
}
