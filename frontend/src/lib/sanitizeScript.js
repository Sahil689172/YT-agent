const STRIP_PATTERNS = [
  /^Narrator:\s*/gim,
  /^Voiceover:\s*/gim,
  /^Scene\s*\d+\s*:\s*/gim,
  /^Here's your script:\s*/gim,
]

/** Remove common script prefixes before sending to the pipeline. */
export function sanitizeScript(text) {
  let out = text
  for (const pattern of STRIP_PATTERNS) {
    out = out.replace(pattern, '')
  }
  return out.replace(/\n{3,}/g, '\n\n').trim()
}
