import { motion } from 'framer-motion'

const variants = {
  primary: 'neo-button text-white border border-white/10',
  secondary:
    'bg-surface-2 text-white/90 border border-white/8 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_4px_16px_rgba(0,0,0,0.4)]',
  ghost: 'bg-transparent text-white/60 border border-white/10 hover:text-white/90 hover:border-white/20',
}

export default function NeoButton({
  children,
  variant = 'primary',
  className = '',
  icon: Icon,
  onClick,
  type = 'button',
  disabled,
}) {
  return (
    <motion.button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`
        inline-flex items-center justify-center gap-2.5 rounded-xl px-6 py-3.5
        text-sm font-semibold tracking-tight transition-colors
        disabled:opacity-40 disabled:pointer-events-none
        ${variants[variant]} ${className}
      `}
      whileHover={disabled ? {} : { y: -2, scale: 1.01 }}
      whileTap={disabled ? {} : { y: 1, scale: 0.99 }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
    >
      {Icon && <Icon size={18} strokeWidth={2} className="opacity-90" />}
      {children}
    </motion.button>
  )
}
