import { motion } from 'framer-motion'
import { AlertCircle } from 'lucide-react'

export default function ErrorBanner({ title, message, onDismiss }) {
  if (!title && !message) return null

  return (
    <motion.div
      className="neo-inset rounded-xl border border-white/10 p-4 flex gap-3"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      role="alert"
    >
      <AlertCircle className="shrink-0 text-white/50 mt-0.5" size={20} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white">{title}</p>
        {message && (
          <p className="text-xs text-white/45 mt-1 leading-relaxed">{message}</p>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="text-xs text-white/40 hover:text-white/70 shrink-0"
        >
          Dismiss
        </button>
      )}
    </motion.div>
  )
}
