import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import CircularProgress from '../components/ui/CircularProgress'
import GlassTerminal from '../components/ui/GlassTerminal'
import NeoButton from '../components/ui/NeoButton'
import { PROCESSING_PHASES } from '../constants/pipeline'

export default function ProcessingPage() {
  const navigate = useNavigate()
  const [phaseIndex, setPhaseIndex] = useState(0)
  const [allLogs, setAllLogs] = useState([])
  const [activeLineIndex, setActiveLineIndex] = useState(-1)
  const [complete, setComplete] = useState(false)
  const timersRef = useRef([])

  const currentPhase = PROCESSING_PHASES[phaseIndex]

  useEffect(() => {
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []

    if (!currentPhase) {
      setComplete(true)
      return
    }

    const logs = currentPhase.logs
    let accumulatedDelay = 300

    logs.forEach((line) => {
      const showTimer = setTimeout(() => {
        setAllLogs((prev) => {
          const next = [...prev, line]
          setActiveLineIndex(next.length - 1)
          return next
        })
      }, accumulatedDelay)
      timersRef.current.push(showTimer)
      accumulatedDelay += line.length * 24 + 700
    })

    const phaseEndTimer = setTimeout(() => {
      if (phaseIndex < PROCESSING_PHASES.length - 1) {
        setPhaseIndex((p) => p + 1)
        setActiveLineIndex(-1)
      } else {
        setComplete(true)
        setActiveLineIndex(-1)
      }
    }, accumulatedDelay + 500)
    timersRef.current.push(phaseEndTimer)

    return () => {
      timersRef.current.forEach(clearTimeout)
      timersRef.current = []
    }
  }, [phaseIndex, currentPhase])

  const progress = complete ? 100 : (currentPhase?.progress ?? 0)

  return (
    <div className="max-w-2xl mx-auto space-y-10">
      <motion.header
        className="text-center"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-white text-glow">
          Building Your Short
        </h1>
        <p className="mt-2 text-white/40 text-sm">Pipeline running in workspace</p>
      </motion.header>

      <motion.div
        className="flex justify-center"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.15 }}
      >
        <div className="neo-panel-elevated rounded-3xl p-8 glow-soft">
          <CircularProgress
            progress={progress}
            label={complete ? 'Complete' : `Phase ${phaseIndex + 1} — ${currentPhase?.label}`}
          />
        </div>
      </motion.div>

      <GlassTerminal lines={allLogs} activeLineIndex={activeLineIndex} />

      {complete && (
        <motion.div
          className="flex justify-center pt-2"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <NeoButton icon={ArrowRight} onClick={() => navigate('/result')}>
            View Results
          </NeoButton>
        </motion.div>
      )}
    </div>
  )
}
