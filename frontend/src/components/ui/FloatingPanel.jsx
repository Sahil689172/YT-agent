import { motion } from 'framer-motion'

export default function FloatingPanel({
  children,
  title,
  icon: Icon,
  className = '',
  delay = 0,
  span,
}) {
  const spanClass =
    span === 'full'
      ? 'col-span-full'
      : span === '2'
        ? 'md:col-span-2'
        : ''

  return (
    <motion.section
      className={`neo-panel-elevated rounded-2xl border border-white/[0.06] overflow-hidden ${spanClass} ${className}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -3, transition: { duration: 0.2 } }}
    >
      {title && (
        <header className="flex items-center gap-2 px-5 py-3.5 border-b border-white/[0.05] bg-surface-2/80">
          {Icon && <Icon size={16} className="text-white/40" strokeWidth={1.75} />}
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">
            {title}
          </h3>
        </header>
      )}
      <div className="p-5">{children}</div>
    </motion.section>
  )
}
