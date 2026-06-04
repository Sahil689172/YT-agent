/**
 * Clean user-pasted script before sending to the API.
 * Keeps narration only; strips meta labels and intro boilerplate.
 */

const LINE_START_PATTERNS = [
  /^here'?s\s+(?:a\s+)?script\s+for\s+(?:your\s+)?youtube\s+shorts?/i,
  /^here\s+is\s+(?:the\s+)?(?:a\s+)?script/i,
  /^here'?s\s+(?:the\s+)?(?:a\s+)?script/i,
  /^this\s+script\s+explains/i,
  /^introduction\s*:/i,
  /^narrator\s*:/i,
  /^voiceover\s*:/i,
  /^host\s*:/i,
  /^speaker\s*:/i,
  /^scene\s*\d+\s*:/i,
  /^title\s*:/i,
  /^script\s*:/i,
]

const INLINE_PATTERNS = [
  /here'?s\s+a\s+script\s+for\s+your\s+youtube\s+shorts?/gi,
  /here\s+is\s+the\s+script/gi,
]

function stripLinePrefix(line) {
  let out = line.trim()
  out = out.replace(/^(narrator|voiceover|host|speaker)\s*:\s*/i, '')
  out = out.replace(/^\[.*?\]\s*/, '')
  out = out.replace(/^\(.*?\)\s*/, '')
  return out.trim()
}

function shouldDropLine(line) {
  const trimmed = line.trim()
  if (!trimmed) return false
  return LINE_START_PATTERNS.some((re) => re.test(trimmed))
}

export function sanitizeScript(raw) {
  if (!raw || typeof raw !== 'string') return ''

  let text = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()

  for (const re of INLINE_PATTERNS) {
    text = text.replace(re, '')
  }

  const lines = text.split('\n')
  const kept = []

  for (const line of lines) {
    if (shouldDropLine(line)) continue
    const cleaned = stripLinePrefix(line)
    if (cleaned) kept.push(cleaned)
  }

  return kept
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
