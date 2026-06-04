import { motion, AnimatePresence } from 'framer-motion'
import { Terminal } from 'lucide-react'
import { useTypingEffect } from '../../hooks/useTypingEffect'

function TypedLine({ text, active }) {
  const displayed = useTypingEffect(text, 22, active)
  const isSuccess = text.includes('[✓]')

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className={`font-mono text-[13px] leading-relaxed ${isSuccess ? 'text-white/90' : 'text-white/45'}`}
    >
      {displayed}
      {active && displayed.length < text.length && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-white/70 animate-pulse align-middle" />
      )}
    </motion.div>
  )
}

export default function GlassTerminal({ lines = [], activeLineIndex = -1 }) {
  return (
    <motion.div
      className="glass-panel rounded-2xl overflow-hidden w-full"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.5 }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06] bg-black/20">
        <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
        <div className="flex-1 flex items-center justify-center gap-2 text-[11px] font-mono text-white/35">
          <Terminal size={12} />
          autoshorts — pipeline
        </div>
      </div>
      <div className="p-5 md:p-6 min-h-[200px] space-y-2">
        <AnimatePresence mode="popLayout">
          {lines.map((line, index) => (
            <TypedLine
              key={`${index}-${line}`}
              text={line}
              active={index === activeLineIndex}
            />
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}
