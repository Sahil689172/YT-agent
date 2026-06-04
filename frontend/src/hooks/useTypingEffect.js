import { useEffect, useState } from 'react'

export function useTypingEffect(text, speed = 28, enabled = true) {
  const [displayed, setDisplayed] = useState('')

  useEffect(() => {
    if (!enabled) {
      setDisplayed(text)
      return
    }

    setDisplayed('')
    let index = 0
    const interval = setInterval(() => {
      index += 1
      setDisplayed(text.slice(0, index))
      if (index >= text.length) clearInterval(interval)
    }, speed)

    return () => clearInterval(interval)
  }, [text, speed, enabled])

  return displayed
}
