import { motion } from 'framer-motion'

export default function ProgressBar({ value = 0, className = '' }) {
  const clamped = Math.min(100, Math.max(0, value))

  return (
    <div
      className={`h-1.5 w-full rounded-full neo-inset overflow-hidden ${className}`}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <motion.div
        className="h-full rounded-full bg-white/80"
        style={{ boxShadow: '0 0 12px rgba(255,255,255,0.25)' }}
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  )
}
