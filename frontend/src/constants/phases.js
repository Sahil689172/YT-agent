/** Pipeline phase labels (match backend job_manager.py). */

export const TOPIC_PHASES = [
  'Script Generation',
  'Metadata Generation',
  'Voice Generation',
  'Caption Generation',
  'Scene Generation',
  'Visual Timeline',
  'Thumbnail Generation',
  'Finalization',
]

export const SCRIPT_PHASES = [
  'Script Preparation',
  'Metadata Generation',
  'Voice Generation',
  'Caption Generation',
  'Scene Generation',
  'Visual Timeline',
  'Thumbnail Generation',
  'Finalization',
]

/**
 * Build terminal lines from API progress.
 * `completed` = number of finished phases; current phase is at index `completed`.
 */
export function buildTerminalLogs(phases, { completed, current_phase, status, error }) {
  if (status === 'completed') {
    return phases.map((p) => `✓ ${p}`)
  }

  if (status === 'failed') {
    const lines = phases.map((p, i) => (i < completed ? `✓ ${p}` : `  ${p}`))
    lines.push(`✗ ${error || `Failed at ${current_phase}`}`)
    return lines
  }

  const lines = []
  phases.forEach((phase, index) => {
    if (index < completed) {
      lines.push(`✓ ${phase}`)
    } else if (index === completed) {
      lines.push(`Running... ${phase}`)
    }
  })

  if (!lines.length) {
    return [`Running... ${current_phase || 'Pipeline'}`]
  }

  return lines
}

export function progressPercent(completed, total) {
  if (!total) return 0
  return Math.min(100, Math.round((completed / total) * 100))
}
