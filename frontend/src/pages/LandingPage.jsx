import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useInView } from 'framer-motion'
import {
  Sparkles,
  Lightbulb,
  FileText,
  Clapperboard,
  Search,
  Video,
  Image,
  Play,
  ArrowRight,
  Mic,
  Captions,
  Layers,
} from 'lucide-react'
import GlassButton from '../components/landing/GlassButton'
import CrowdCanvas from '../components/landing/CrowdCanvas'

const FEATURES = [
  {
    title: 'AI Topic Mode',
    description: 'Drop a topic — the pipeline writes a tight Shorts script for you.',
    icon: Lightbulb,
  },
  {
    title: 'Custom Script Mode',
    description: 'Paste narration and ship with your exact voice and pacing.',
    icon: FileText,
  },
  {
    title: 'Scene Planning',
    description: 'LLM-driven beats aligned to every line of your script.',
    icon: Clapperboard,
  },
  {
    title: 'Visual Search',
    description: 'Stock video and imagery matched scene-by-scene.',
    icon: Search,
  },
  {
    title: 'Video Generation',
    description: 'Voice, captions, cuts, and export — one automated pass.',
    icon: Video,
  },
  {
    title: 'Thumbnail Creation',
    description: 'Click-worthy covers from your timeline or AI fallback.',
    icon: Image,
  },
]

const PIPELINE = [
  { label: 'Topic / Script', icon: FileText },
  { label: 'Voice', icon: Mic },
  { label: 'Captions', icon: Captions },
  { label: 'Scenes', icon: Layers },
  { label: 'Visual Search', icon: Search },
  { label: 'Video', icon: Video },
  { label: 'Thumbnail', icon: Image },
]

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.65, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] },
  }),
}

function Section({ id, className = '', children }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <motion.section
      id={id}
      ref={ref}
      initial="hidden"
      animate={inView ? 'visible' : 'hidden'}
      variants={fadeUp}
      className={className}
    >
      {children}
    </motion.section>
  )
}

export default function LandingPage() {
  const scrollToDemo = () => {
    document.getElementById('pipeline')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-white text-black">
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-black/[0.06] bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 md:px-8">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-black/10 bg-neutral-50 shadow-sm transition-shadow group-hover:shadow-md">
              <Sparkles size={18} className="text-black" strokeWidth={1.75} />
            </div>
            <span className="text-lg font-semibold tracking-tight text-black">AutoShorts</span>
          </Link>
          <GlassButton to="/create" variant="secondary" className="!px-5 !py-2.5 text-xs">
            Get Started
          </GlassButton>
        </div>
      </header>

      {/* Hero + crowd: one viewport — crowd overlaps lower ~40%, visible on load */}
      <section className="relative min-h-[100dvh] min-h-screen bg-white">
        <div
          className="pointer-events-none absolute inset-0 z-0"
          style={{
            background:
              'radial-gradient(ellipse 90% 45% at 50% 0%, rgba(0,0,0,0.04) 0%, transparent 50%)',
          }}
        />

        <div className="relative z-20 mx-auto w-full max-w-5xl px-5 pt-[4.75rem] text-center sm:pt-24 md:px-8">
          <motion.p
            className="mb-2 text-[11px] font-semibold uppercase tracking-[0.26em] text-black/40"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.05 }}
          >
            AI Shorts Studio
          </motion.p>
          <motion.h1
            className="mx-auto max-w-4xl text-[1.75rem] font-semibold leading-[1.02] tracking-tight text-black sm:text-4xl md:text-[2.65rem] lg:text-[3.1rem]"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
          >
            Turn Ideas Into Viral Shorts
          </motion.h1>
          <motion.p
            className="mx-auto mt-3 max-w-2xl text-base font-light text-black/55 md:text-lg"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.22 }}
          >
            Generate videos, thumbnails, captions, scenes, and metadata in minutes.
          </motion.p>
          <motion.div
            className="mt-5 flex flex-wrap items-center justify-center gap-3 sm:gap-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.32 }}
          >
            <GlassButton to="/create" icon={ArrowRight}>
              Get Started
            </GlassButton>
            <GlassButton variant="secondary" icon={Play} onClick={scrollToDemo}>
              Watch Demo
            </GlassButton>
          </motion.div>
        </div>

        <div
          id="crowd"
          aria-label="Creators walking"
          className="pointer-events-none absolute inset-x-0 bottom-0 top-[54%] z-10 sm:top-[52%] md:top-[50%]"
        >
          <CrowdCanvas maxCrowd={60} />
        </div>
      </section>

      {/* Capabilities — below the fold hero */}
      <Section
        id="features"
        className="relative z-20 mx-auto max-w-6xl overflow-hidden bg-white px-5 pb-24 pt-10 md:px-8 md:pb-32 md:pt-14"
      >
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden
          style={{
            background:
              'radial-gradient(ellipse 70% 50% at 15% 20%, rgba(0,0,0,0.03), transparent 50%), radial-gradient(ellipse 60% 45% at 85% 80%, rgba(0,0,0,0.04), transparent 55%)',
          }}
        />
        <div className="relative mb-14 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-black/40">
            Capabilities
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-black md:text-4xl">
            Everything in one pipeline
          </h2>
        </div>
        <div className="relative grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.article
              key={f.title}
              custom={i}
              variants={fadeUp}
              className="glass-card group rounded-2xl p-6 transition-all duration-300"
              whileHover={{ y: -4, scale: 1.01 }}
            >
              <div className="glass-card-icon mb-4 flex h-11 w-11 items-center justify-center rounded-xl text-black transition-transform duration-300 group-hover:scale-105">
                <f.icon size={20} strokeWidth={1.75} />
              </div>
              <h3 className="text-lg font-semibold tracking-tight text-black">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-black/55">{f.description}</p>
            </motion.article>
          ))}
        </div>
      </Section>

      {/* Pipeline */}
      <Section
        id="pipeline"
        className="relative z-10 border-t border-black/[0.06] bg-neutral-50 py-24 md:py-32"
      >
        <div className="mx-auto max-w-4xl px-5 md:px-8">
          <div className="mb-16 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-black/40">
              Workflow
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-black md:text-4xl">
              From idea to publish-ready
            </h2>
          </div>

          <div className="relative flex flex-col items-center gap-0">
            {PIPELINE.map((step, i) => (
              <div key={step.label} className="flex w-full max-w-md flex-col items-center">
                <motion.div
                  className="flex w-full items-center gap-4 rounded-2xl border border-black/[0.08] bg-white px-5 py-4 shadow-sm"
                  initial={{ opacity: 0, x: -12 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06, duration: 0.45 }}
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-black/10 bg-neutral-50">
                    <step.icon size={18} className="text-black/70" />
                  </div>
                  <span className="text-sm font-medium tracking-tight text-black">{step.label}</span>
                </motion.div>
                {i < PIPELINE.length - 1 && (
                  <motion.div
                    className="flex h-10 flex-col items-center justify-center"
                    initial={{ scaleY: 0 }}
                    whileInView={{ scaleY: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.08 + 0.1, duration: 0.35 }}
                  >
                    <div className="h-full w-px bg-gradient-to-b from-black/20 via-black/10 to-black/20" />
                    <span className="my-1 text-black/30 text-xs">↓</span>
                    <div className="h-full w-px bg-gradient-to-b from-black/10 via-black/20 to-black/10" />
                  </motion.div>
                )}
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* CTA */}
      <Section className="relative z-10 mx-auto max-w-3xl px-5 py-24 text-center md:px-8 md:py-32">
        <h2 className="text-3xl font-semibold tracking-tight text-black md:text-4xl">
          Ready to Create Your First Short?
        </h2>
        <p className="mt-4 font-light text-black/55">
          Join creators moving forward — AutoShorts handles the heavy lifting.
        </p>
        <div className="mt-10 flex justify-center">
          <GlassButton to="/create" icon={ArrowRight}>
            Get Started
          </GlassButton>
        </div>
      </Section>

      <footer className="border-t border-black/[0.06] py-8 text-center text-xs text-black/40">
        AutoShorts · Crowd art via{' '}
        <a
          href="https://www.openpeeps.com/"
          className="underline hover:text-black/70"
          target="_blank"
          rel="noreferrer"
        >
          Open Peeps
        </a>{' '}
        (CC0)
      </footer>
    </div>
  )
}
