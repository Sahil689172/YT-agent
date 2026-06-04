import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import AnimatedLogo from '../ui/AnimatedLogo'
import RotatingLoader from '../ui/RotatingLoader'
import { SPLASH_STATUSES } from '../../constants/pipeline'

export default function SplashScreen({ onComplete }) {
  const [statusIndex, setStatusIndex] = useState(0)
  const [fadeOut, setFadeOut] = useState(false)

  useEffect(() => {
    const statusTimer = setInterval(() => {
      setStatusIndex((i) => (i < SPLASH_STATUSES.length - 1 ? i + 1 : i))
    }, 900)

    const fadeTimer = setTimeout(() => setFadeOut(true), 3000)
    const completeTimer = setTimeout(() => onComplete?.(), 3800)

    return () => {
      clearInterval(statusTimer)
      clearTimeout(fadeTimer)
      clearTimeout(completeTimer)
    }
  }, [onComplete])

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-bg px-6"
      animate={{ opacity: fadeOut ? 0 : 1 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse 50% 40% at 50% 45%, rgba(255,255,255,0.06), transparent 70%)',
            }}
          />

          <motion.div
            className="relative flex flex-col items-center text-center max-w-md"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          >
            <AnimatedLogo />

            <motion.h1
              className="mt-10 text-4xl md:text-5xl font-semibold tracking-tight text-white text-glow"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.25, duration: 0.6 }}
            >
              AutoShorts
            </motion.h1>

            <motion.p
              className="mt-3 text-base md:text-lg text-white/45 font-light tracking-wide"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              Turn Ideas Into Shorts In Minutes
            </motion.p>

            <motion.div
              className="mt-12 flex flex-col items-center gap-4 text-white/55"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.55 }}
            >
              <RotatingLoader size={44} />
              <span className="text-sm font-medium tracking-wide text-white/60">
                ◌ Generating Content
              </span>
            </motion.div>

            <div className="mt-8 h-6 relative w-full flex justify-center">
              <AnimatePresence mode="wait">
                <motion.p
                  key={statusIndex}
                  className="text-sm font-mono text-white/35 absolute"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.35 }}
                >
                  {SPLASH_STATUSES[statusIndex]}
                </motion.p>
              </AnimatePresence>
            </div>
          </motion.div>
    </motion.div>
  )
}
