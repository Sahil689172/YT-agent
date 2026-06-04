import { useEffect, useRef } from 'react'

const VIDEO_SRC =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260530_042513_df96a13b-6155-4f6e-8b93-c9dee66fba08.mp4'

const HEAD_ANCHOR = { x: 0.5, y: 0.36 }
const H_REACH = 0.78
const V_INFLUENCE = 0.08

/** Spring — higher = snappier follow */
const STIFFNESS = 32
const DAMPING = 11
/** Pointer input smoothing (reduces micro-jitter) */
const POINTER_SMOOTH = 0.42
/** Min seconds between seek attempts while already seeking */
const SEEK_EPS = 0.005

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v))
}

export default function StudioAgentVideo({ className = '' }) {
  const panelRef = useRef(null)
  const videoRef = useRef(null)

  useEffect(() => {
    const video = videoRef.current
    const panel = panelRef.current
    if (!video || !panel) return undefined

    const state = {
      ready: false,
      pointerNorm: 0.5,
      targetNorm: 0.5,
      norm: 0.5,
      normVel: 0,
      latestSeekTime: 0.5,
      seeking: false,
      lastFrame: 0,
    }

    const cursorToNorm = (clientX, clientY) => {
      const rect = panel.getBoundingClientRect()
      const headX = rect.left + rect.width * HEAD_ANCHOR.x
      const headY = rect.top + rect.height * HEAD_ANCHOR.y
      const dx = clientX - headX
      const dy = clientY - headY
      const hSpan = Math.max(rect.width * H_REACH, window.innerWidth * 0.42)
      const vSpan = rect.height * 0.5
      let norm = 0.5 + dx / hSpan + (dy / vSpan) * V_INFLUENCE
      return clamp(norm, 0.03, 0.97)
    }

    const applySeek = (time) => {
      if (!state.ready || !video.duration) return
      state.latestSeekTime = clamp(time, 0, video.duration)
      if (state.seeking) return
      if (Math.abs(video.currentTime - state.latestSeekTime) < SEEK_EPS) return

      state.seeking = true
      try {
        if (typeof video.fastSeek === 'function') {
          video.fastSeek(state.latestSeekTime)
        } else {
          video.currentTime = state.latestSeekTime
        }
      } catch {
        video.currentTime = state.latestSeekTime
      }
    }

    const onSeeked = () => {
      state.seeking = false
      if (
        state.ready &&
        Math.abs(video.currentTime - state.latestSeekTime) > SEEK_EPS
      ) {
        applySeek(state.latestSeekTime)
      }
    }

    const warmDecoder = async () => {
      if (!video.duration) return
      const marks = [0.02, 0.5, 0.98].map((n) => n * video.duration)
      for (const t of marks) {
        video.currentTime = t
        await new Promise((resolve) => {
          const done = () => {
            video.removeEventListener('seeked', done)
            resolve()
          }
          video.addEventListener('seeked', done)
        })
      }
      video.currentTime = video.duration * 0.5
      state.norm = 0.5
      state.targetNorm = 0.5
      state.pointerNorm = 0.5
    }

    let warming = false

    const onReady = () => {
      if (!video.duration || state.ready) return
      state.ready = true
      applySeek(video.duration * 0.5)
      if (!warming) {
        warming = true
        warmDecoder().finally(() => {
          warming = false
        })
      }
    }

    const onPointer = (clientX, clientY) => {
      if (!state.ready) return
      const raw = cursorToNorm(clientX, clientY)
      state.pointerNorm += (raw - state.pointerNorm) * POINTER_SMOOTH
      state.targetNorm = state.pointerNorm
    }

    const onMove = (e) => onPointer(e.clientX, e.clientY)
    const onTouch = (e) => {
      if (e.touches[0]) onPointer(e.touches[0].clientX, e.touches[0].clientY)
    }
    const onLeave = () => {
      state.targetNorm = 0.5
    }

    let rafId = 0

    const tick = (now) => {
      if (!state.lastFrame) state.lastFrame = now
      const dt = Math.min((now - state.lastFrame) / 1000, 0.04)
      state.lastFrame = now

      if (state.ready && video.duration) {
        const target = state.targetNorm
        const force = (target - state.norm) * STIFFNESS
        state.normVel += force * dt
        state.normVel *= Math.exp(-DAMPING * dt)
        state.norm += state.normVel * dt
        state.norm = clamp(state.norm, 0.03, 0.97)

        applySeek(state.norm * video.duration)
      }

      rafId = requestAnimationFrame(tick)
    }

    rafId = requestAnimationFrame(tick)

    video.addEventListener('loadedmetadata', onReady)
    video.addEventListener('canplaythrough', onReady)
    video.addEventListener('seeked', onSeeked)
    document.addEventListener('mousemove', onMove, { passive: true })
    document.addEventListener('touchmove', onTouch, { passive: true })
    document.addEventListener('mouseleave', onLeave)

    if (video.readyState >= 2) onReady()

    return () => {
      cancelAnimationFrame(rafId)
      video.removeEventListener('loadedmetadata', onReady)
      video.removeEventListener('canplaythrough', onReady)
      video.removeEventListener('seeked', onSeeked)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('touchmove', onTouch)
      document.removeEventListener('mouseleave', onLeave)
    }
  }, [])

  return (
    <div
      ref={panelRef}
      className={`studio-agent-panel relative flex h-full w-full items-center justify-center ${className}`}
      aria-hidden
    >
      <div className="studio-agent-glow pointer-events-none absolute inset-0" />
      <video
        ref={videoRef}
        className="studio-agent-video relative z-[1] h-full w-full object-contain object-center will-change-transform"
        muted
        playsInline
        preload="auto"
        src={VIDEO_SRC}
      />
    </div>
  )
}
