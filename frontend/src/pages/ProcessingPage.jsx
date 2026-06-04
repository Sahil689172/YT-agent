import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Home, Loader2 } from 'lucide-react'
import CircularProgress from '../components/ui/CircularProgress'
import GlassTerminal from '../components/ui/GlassTerminal'
import ProgressBar from '../components/ui/ProgressBar'
import ErrorBanner from '../components/ui/ErrorBanner'
import NeoButton from '../components/ui/NeoButton'
import RotatingLoader from '../components/ui/RotatingLoader'
import { useGeneration } from '../context/GenerationContext'
import { ApiError } from '../lib/api'
import {
  TOPIC_PHASES,
  SCRIPT_PHASES,
  buildTerminalLogs,
  buildPerformanceLines,
  progressPercent,
} from '../constants/phases'

const POLL_MS = 2000

export default function ProcessingPage() {
  const navigate = useNavigate()
  const {
    jobId,
    mode,
    progress,
    refreshProgress,
    fetchAndStoreResult,
    error,
    clearJob,
  } = useGeneration()

  const [pollError, setPollError] = useState(null)
  const navigatingRef = useRef(false)
  const phases = mode === 'script' ? SCRIPT_PHASES : TOPIC_PHASES

  useEffect(() => {
    if (!jobId) {
      navigate('/', { replace: true })
    }
  }, [jobId, navigate])

  useEffect(() => {
    if (!jobId) return undefined

    let cancelled = false

    async function poll() {
      try {
        const data = await refreshProgress(jobId)
        if (cancelled || navigatingRef.current) return

        setPollError(null)

        if (data.status === 'completed') {
          navigatingRef.current = true
          await fetchAndStoreResult(jobId)
          if (!cancelled) navigate('/result', { replace: true })
          return
        }

        if (data.status === 'failed') {
          setPollError(
            new ApiError(
              'Generation Failed',
              data.error || 'Pipeline failed. Check the API logs.',
            ),
          )
        }
      } catch (err) {
        if (cancelled) return
        setPollError(
          err instanceof ApiError
            ? err
            : new ApiError('Network Error', err?.message || 'Lost connection to API.'),
        )
      }
    }

    poll()
    const id = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [jobId, refreshProgress, fetchAndStoreResult, navigate])

  const terminalLines = useMemo(() => {
    if (!progress) {
      return ['Connecting to pipeline…', 'Waiting for job status…']
    }
    return buildTerminalLogs(phases, {
      ...progress,
      error: progress.error,
    })
  }, [phases, progress])

  const performanceLines = useMemo(
    () => buildPerformanceLines(progress),
    [progress],
  )

  const percent = progress
    ? progressPercent(progress.completed, progress.total)
    : 0

  const activeLineIndex = terminalLines.findIndex((l) => l.startsWith('Running'))
  const displayError = pollError || error
  const isRunning =
    progress?.status === 'running' ||
    progress?.status === 'queued' ||
    !progress

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <motion.header
        className="text-center"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex justify-center mb-6">
          <RotatingLoader size={52} />
        </div>
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-white text-glow">
          Building Your Short
        </h1>
        <p className="mt-2 text-white/40 text-sm">
          {progress?.current_phase || 'Initializing pipeline…'}
        </p>
      </motion.header>

      {displayError && (
        <ErrorBanner
          title={displayError.title}
          message={displayError.message}
        />
      )}

      <motion.div
        className="space-y-4"
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <div className="neo-panel-elevated rounded-3xl p-8 glow-soft flex justify-center">
          <CircularProgress
            progress={isRunning && percent < 100 ? Math.max(percent, 5) : percent}
            label={
              progress
                ? `${progress.completed} / ${progress.total} — ${progress.current_phase}`
                : 'Starting…'
            }
          />
        </div>
        <ProgressBar value={percent} />
        {progress && (
          <p className="text-center text-xs text-white/35 font-mono">
            {progress.status === 'queued' ? 'Queued — waiting for pipeline' : 'Live from API'}
          </p>
        )}
      </motion.div>

      <GlassTerminal
        lines={terminalLines}
        activeLineIndex={activeLineIndex >= 0 ? activeLineIndex : -1}
      />

      {performanceLines.length > 0 && (
        <motion.div
          className="neo-panel rounded-2xl p-5 font-mono text-sm text-white/70 space-y-1"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <p className="text-white/45 text-xs uppercase tracking-wider mb-2">
            Performance
          </p>
          {performanceLines.map((line) => (
            <p
              key={line}
              className={
                line.startsWith('TOTAL:')
                  ? 'text-emerald-400/90 pt-2 border-t border-white/10 mt-2'
                  : ''
              }
            >
              {line}
            </p>
          ))}
        </motion.div>
      )}

      {isRunning && !displayError && (
        <div className="flex items-center justify-center gap-2 text-white/40 text-sm">
          <Loader2 size={16} className="animate-spin" />
          Polling every 2 seconds…
        </div>
      )}

      {displayError && (
        <div className="flex justify-center gap-3">
          <NeoButton variant="ghost" icon={Home} onClick={() => {
            clearJob()
            navigate('/')
          }}>
            Return Home
          </NeoButton>
        </div>
      )}
    </div>
  )
}
