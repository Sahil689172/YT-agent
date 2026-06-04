import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Film,
  Image,
  Type,
  AlignLeft,
  Hash,
  Download,
  Home,
  FileDown,
} from 'lucide-react'
import FloatingPanel from '../components/ui/FloatingPanel'
import NeoButton from '../components/ui/NeoButton'
import { RESULT_PLACEHOLDER } from '../constants/pipeline'

function MediaPlaceholder({ aspect, label, icon: Icon }) {
  return (
    <div
      className={`neo-inset rounded-xl flex flex-col items-center justify-center gap-3 border border-white/[0.04] ${aspect}`}
    >
      <div className="h-14 w-14 rounded-xl neo-panel flex items-center justify-center">
        <Icon size={28} className="text-white/25" strokeWidth={1.25} />
      </div>
      <p className="text-xs text-white/30 text-center px-4 max-w-[200px]">{label}</p>
    </div>
  )
}

export default function ResultPage() {
  const navigate = useNavigate()
  const { title, description, hashtags } = RESULT_PLACEHOLDER

  const handleDownload = (type) => void type

  return (
    <div className="space-y-8 md:space-y-10">
      <motion.header
        className="text-center md:text-left"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/30 mb-2">
          Export Dashboard
        </p>
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-white text-glow">
          Your Short Is Ready
        </h1>
        <p className="mt-2 text-white/40 text-sm max-w-xl">
          Preview placeholders — assets populate when the backend connects
        </p>
      </motion.header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 md:gap-6">
        <FloatingPanel title="Video Preview" icon={Film} delay={0.05} span="2">
          <MediaPlaceholder
            aspect="aspect-[9/16] max-h-[420px] w-full max-w-[280px] mx-auto"
            label="Final MP4 (1080×1920) will render here"
            icon={Film}
          />
        </FloatingPanel>

        <FloatingPanel title="Thumbnail Preview" icon={Image} delay={0.1}>
          <MediaPlaceholder
            aspect="aspect-video w-full"
            label="Thumbnail (1280×720) will render here"
            icon={Image}
          />
        </FloatingPanel>

        <FloatingPanel title="Title" icon={Type} delay={0.15}>
          <p className="text-lg font-semibold text-white leading-snug">{title}</p>
        </FloatingPanel>

        <FloatingPanel title="Description" icon={AlignLeft} delay={0.2} span="2">
          <p className="text-sm text-white/50 leading-relaxed">{description}</p>
        </FloatingPanel>

        <FloatingPanel title="Hashtags" icon={Hash} delay={0.25}>
          <div className="flex flex-wrap gap-2">
            {hashtags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-3 py-1.5 rounded-full neo-inset text-white/50 border border-white/[0.04]"
              >
                #{tag}
              </span>
            ))}
          </div>
        </FloatingPanel>

        <FloatingPanel title="Downloads" icon={Download} delay={0.3} span="full">
          <div className="flex flex-col sm:flex-row flex-wrap gap-3">
            <NeoButton
              variant="secondary"
              icon={FileDown}
              className="flex-1 min-w-[160px]"
              onClick={() => handleDownload('video')}
            >
              Download Video
            </NeoButton>
            <NeoButton
              variant="secondary"
              icon={Image}
              className="flex-1 min-w-[160px]"
              onClick={() => handleDownload('thumbnail')}
            >
              Download Thumbnail
            </NeoButton>
            <NeoButton
              variant="secondary"
              icon={Download}
              className="flex-1 min-w-[160px]"
              onClick={() => handleDownload('metadata')}
            >
              Download Metadata
            </NeoButton>
          </div>
        </FloatingPanel>
      </div>

      <motion.div
        className="flex justify-center pt-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <NeoButton variant="ghost" icon={Home} onClick={() => navigate('/')}>
          Return Home
        </NeoButton>
      </motion.div>
    </div>
  )
}
