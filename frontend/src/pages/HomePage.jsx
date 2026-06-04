import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Lightbulb, FileText, Sparkles, Info, Loader2 } from 'lucide-react'
import NeoCard from '../components/ui/NeoCard'
import NeoInput from '../components/ui/NeoInput'
import NeoTextarea from '../components/ui/NeoTextarea'
import NeoButton from '../components/ui/NeoButton'
import ErrorBanner from '../components/ui/ErrorBanner'
import { useGeneration } from '../context/GenerationContext'
import { ApiError } from '../lib/api'

const SCRIPT_RULES = [
  'Recommended 80–100 words',
  'Generates 30–45 second videos',
  'Large scripts may fail',
]

export default function HomePage() {
  const navigate = useNavigate()
  const { startTopic, startScript, loading, error, clearJob } = useGeneration()
  const [topic, setTopic] = useState('')
  const [script, setScript] = useState('')
  const [localError, setLocalError] = useState(null)

  const displayError = localError || error

  async function handleTopicGenerate() {
    setLocalError(null)
    clearJob()
    try {
      await startTopic(topic)
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
    const topicLabel = topic.trim() || 'Custom Script'
    try {
      await startScript(script, topicLabel)
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
    <div className="space-y-12 md:space-y-16">
      <motion.header
        className="text-center max-w-2xl mx-auto"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <motion.p
          className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/30 mb-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          AI Shorts Studio
        </motion.p>
        <h1 className="text-4xl md:text-5xl lg:text-[3.25rem] font-semibold tracking-tight text-white text-glow leading-[1.1]">
          Create Your Next Short
        </h1>
        <p className="mt-4 text-lg text-white/45 font-light">
          Turn Ideas Into Shorts In Minutes
        </p>
      </motion.header>

      {displayError && (
        <ErrorBanner
          title={displayError.title}
          message={displayError.message}
          onDismiss={() => {
            setLocalError(null)
            clearJob()
          }}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-2 lg:gap-8">
        <NeoCard
          badge="Mode 01"
          title="Topic Mode"
          subtitle="Start with an idea — the pipeline crafts your script"
          icon={Lightbulb}
          delay={0.1}
        >
          <div className="space-y-5">
            <NeoInput
              id="topic"
              label="YouTube Shorts Topic"
              icon={Sparkles}
              placeholder='e.g. What is EBITDA?'
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={loading}
            />
            <NeoButton
              className={`w-full ${loading ? '[&_svg]:animate-spin' : ''}`}
              icon={loading ? Loader2 : Sparkles}
              onClick={handleTopicGenerate}
              disabled={loading || !topic.trim()}
            >
              {loading ? 'Starting…' : 'Generate Video'}
            </NeoButton>
          </div>
        </NeoCard>

        <NeoCard
          badge="Mode 02"
          title="Custom Script Mode"
          subtitle="Paste plain narration — no JSON or markdown required"
          icon={FileText}
          delay={0.2}
        >
          <div className="space-y-5">
            <NeoTextarea
              id="script"
              label="Your Script"
              placeholder="EBITDA stands for Earnings Before Interest, Taxes, Depreciation, and Amortization..."
              value={script}
              onChange={(e) => setScript(e.target.value)}
              disabled={loading}
            />
            <ul className="neo-inset rounded-xl p-4 space-y-2 border border-white/[0.04]">
              {SCRIPT_RULES.map((rule) => (
                <li key={rule} className="flex items-start gap-2 text-xs text-white/40">
                  <Info size={14} className="shrink-0 mt-0.5 text-white/25" />
                  {rule}
                </li>
              ))}
            </ul>
            <NeoButton
              className={`w-full ${loading ? '[&_svg]:animate-spin' : ''}`}
              icon={loading ? Loader2 : FileText}
              onClick={handleScriptGenerate}
              disabled={loading || !script.trim()}
            >
              {loading ? 'Starting…' : 'Generate Video'}
            </NeoButton>
          </div>
        </NeoCard>
      </div>
    </div>
  )
}
