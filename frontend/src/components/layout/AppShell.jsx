import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Home, Sparkles } from 'lucide-react'

export default function AppShell({ children }) {
  const location = useLocation()
  const isHome = location.pathname === '/'

  return (
    <div className="min-h-screen flex flex-col">
      <motion.header
        className="sticky top-0 z-50 border-b border-white/[0.04] bg-bg/80 backdrop-blur-xl"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 md:px-8">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="h-10 w-10 neo-panel-elevated rounded-xl flex items-center justify-center border border-white/10 group-hover:glow-soft transition-shadow">
              <Sparkles size={18} className="text-white/85" strokeWidth={1.75} />
            </div>
            <span className="text-lg font-semibold tracking-tight text-white group-hover:text-glow transition-all">
              AutoShorts
            </span>
          </Link>

          {!isHome && (
            <Link
              to="/"
              className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/50 border border-white/10 hover:text-white/90 hover:border-white/20 transition-colors neo-inset"
            >
              <Home size={16} />
              Home
            </Link>
          )}
        </div>
      </motion.header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-5 py-8 md:px-8 md:py-12">
        {children}
      </main>
    </div>
  )
}
