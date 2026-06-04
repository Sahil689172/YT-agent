import { useEffect, useState } from 'react'

/**
 * Reveals text one character at a time (Mainframe-style intro).
 */
export function useTypewriter(text, { speed = 38, startDelay = 600, enabled = true } = {}) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!enabled) {
      setDisplayed('')
      setDone(false)
      return undefined
    }

    setDisplayed('')
    setDone(false)
    let index = 0
    let intervalId

    const delayId = setTimeout(() => {
      intervalId = setInterval(() => {
        index += 1
        setDisplayed(text.slice(0, index))
        if (index >= text.length) {
          clearInterval(intervalId)
          setDone(true)
        }
      }, speed)
    }, startDelay)

    return () => {
      clearTimeout(delayId)
      if (intervalId) clearInterval(intervalId)
    }
  }, [text, speed, startDelay, enabled])

  return { displayed, done }
}

/**
 * Types multiple lines in sequence; calls onAllDone when finished.
 */
export function useSequentialTypewriter(lines, { speed = 38, startDelay = 600, linePause = 400 } = {}) {
  const [lineIndex, setLineIndex] = useState(0)
  const current = lines[lineIndex] ?? ''
  const { displayed, done } = useTypewriter(current, {
    speed,
    startDelay: lineIndex === 0 ? startDelay : linePause,
    enabled: lineIndex < lines.length,
  })

  useEffect(() => {
    if (!done || lineIndex >= lines.length - 1) return undefined
    const t = setTimeout(() => setLineIndex((i) => i + 1), linePause)
    return () => clearTimeout(t)
  }, [done, lineIndex, lines.length, linePause])

  const allDone = done && lineIndex >= lines.length - 1
  const completedLines = lines.slice(0, lineIndex)
  const allDisplayed = [...completedLines, displayed]

  return { lines: allDisplayed, currentLine: lineIndex, done: allDone }
}
