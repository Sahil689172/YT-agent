import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

export default function AnimatedLogo({ size = 'lg' }) {
  const dimensions = size === 'sm' ? 'h-14 w-14' : 'h-20 w-20'
  const iconSize = size === 'sm' ? 22 : 32

  return (
    <motion.div
      className={`relative ${dimensions} flex items-center justify-center`}
      initial={{ scale: 0.85, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
    >
      <motion.div
        className="absolute inset-0 rounded-2xl bg-white/5 ring-glow"
        animate={{
          boxShadow: [
            '0 0 24px rgba(255,255,255,0.08)',
            '0 0 48px rgba(255,255,255,0.14)',
            '0 0 24px rgba(255,255,255,0.08)',
          ],
        }}
        transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className={`relative ${dimensions} neo-panel-elevated rounded-2xl flex items-center justify-center border border-white/10`}
        animate={{ rotate: [0, 2, -2, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
      >
        <Sparkles size={iconSize} className="text-white/90" strokeWidth={1.5} />
      </motion.div>
      <motion.div
        className="absolute -inset-3 rounded-3xl border border-white/5"
        animate={{ scale: [1, 1.06, 1], opacity: [0.4, 0.15, 0.4] }}
        transition={{ duration: 2.5, repeat: Infinity }}
      />
    </motion.div>
  )
}
