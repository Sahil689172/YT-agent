import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

const styles = {
  primary:
    'bg-black text-white border border-black shadow-[0_4px_24px_rgba(0,0,0,0.12)] hover:bg-neutral-900',
  secondary:
    'bg-white text-black border border-black/15 shadow-[0_2px_12px_rgba(0,0,0,0.06)] hover:border-black/25 hover:bg-neutral-50',
}

export default function GlassButton({
  children,
  variant = 'primary',
  to,
  href,
  onClick,
  icon: Icon,
  className = '',
}) {
  const base = `
    inline-flex items-center justify-center gap-2.5 rounded-2xl px-7 py-3.5
    text-sm font-semibold tracking-tight transition-colors
    ${styles[variant]} ${className}
  `

  const motionProps = {
    whileHover: { y: -2, scale: 1.02 },
    whileTap: { y: 1, scale: 0.98 },
    transition: { type: 'spring', stiffness: 420, damping: 26 },
  }

  if (to) {
    return (
      <motion.div {...motionProps} className="inline-block">
        <Link to={to} className={base}>
          {Icon && <Icon size={18} strokeWidth={2} className="opacity-90" />}
          {children}
        </Link>
      </motion.div>
    )
  }

  if (href) {
    return (
      <motion.a href={href} className={base} {...motionProps}>
        {Icon && <Icon size={18} strokeWidth={2} className="opacity-90" />}
        {children}
      </motion.a>
    )
  }

  return (
    <motion.button type="button" onClick={onClick} className={base} {...motionProps}>
      {Icon && <Icon size={18} strokeWidth={2} className="opacity-90" />}
      {children}
    </motion.button>
  )
}
