import { motion } from 'framer-motion'

export default function NeoCard({
  children,
  className = '',
  elevated = true,
  delay = 0,
  icon: Icon,
  title,
  subtitle,
  badge,
}) {
  const panelClass = elevated ? 'neo-panel-elevated' : 'neo-panel'

  return (
    <motion.article
      className={`${panelClass} rounded-2xl border border-white/[0.06] p-6 md:p-7 ${className}`}
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -4, transition: { duration: 0.25 } }}
    >
      {(title || Icon) && (
        <header className="flex items-start gap-4 mb-6">
          {Icon && (
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl neo-inset border border-white/5">
              <Icon size={22} className="text-white/80" strokeWidth={1.75} />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              {badge && (
                <span className="text-[10px] font-semibold uppercase tracking-widest text-white/35 px-2 py-0.5 rounded-md bg-white/5 border border-white/5">
                  {badge}
                </span>
              )}
              <h2 className="text-lg font-semibold tracking-tight text-white">{title}</h2>
            </div>
            {subtitle && <p className="text-sm text-white/45 leading-relaxed">{subtitle}</p>}
          </div>
        </header>
      )}
      {children}
    </motion.article>
  )
}
