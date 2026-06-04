import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Sparkles, ArrowLeft } from 'lucide-react'

export default function CreateNav() {
  return (
    <motion.header
      className="fixed top-0 left-0 right-0 z-50 px-5 py-4 sm:px-8 sm:py-5"
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="mx-auto flex max-w-[1200px] items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-white/90 hover:text-white transition-colors">
          <Sparkles size={20} strokeWidth={1.75} className="text-white/80" />
          <span className="text-lg font-semibold tracking-tight sm:text-xl">AutoShorts</span>
        </Link>

        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/[0.04] px-4 py-2 text-sm font-medium text-white/75 backdrop-blur-md transition-all hover:border-white/20 hover:bg-white/[0.08] hover:text-white"
        >
          <ArrowLeft size={15} />
          Back to Home
        </Link>
      </div>
    </motion.header>
  )
}
