import { motion } from 'framer-motion'

export default function RotatingLoader({ size = 48 }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <motion.div
        className="absolute inset-0 rounded-full border-2 border-white/10"
        style={{ borderTopColor: 'rgba(255,255,255,0.7)' }}
        animate={{ rotate: 360 }}
        transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
      />
      <motion.div
        className="absolute inset-1.5 rounded-full border border-white/5"
        style={{ borderBottomColor: 'rgba(255,255,255,0.25)' }}
        animate={{ rotate: -360 }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
      />
      <div className="absolute inset-0 flex items-center justify-center text-white/40 text-xs font-medium">
        ◌
      </div>
    </div>
  )
}
