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

/**
 * Format performance lines for the processing terminal.
 * Uses API phase_timings when available; falls back to performance_summary strings.
 */
/** @param {object | null | undefined} data progress or result payload from API */
export function buildPerformanceLines(data) {
  if (!data) return []

  const timings = data.phase_timings
  if (Array.isArray(timings) && timings.length > 0) {
    const lines = timings.map((t) => {
      const sec = Number(t.duration_seconds)
      const duration = Number.isFinite(sec) ? `${sec.toFixed(1)} sec` : '—'
      return `${t.label}: ${duration}`
    })
    const total = data.total_duration_seconds
    if (total != null && Number.isFinite(Number(total))) {
      lines.push(`TOTAL: ${Number(total).toFixed(1)} sec`)
    }
    return lines
  }

  const summary = data.performance_summary
  if (Array.isArray(summary) && summary.length > 0) {
    return summary
  }

  return []
}

/** Full text for clipboard — includes START/END when timings are present. */
export function formatPerformanceForCopy(data) {
  if (!data) return ''

  const timings = data.phase_timings
  if (Array.isArray(timings) && timings.length > 0) {
    const blocks = timings.map((t) => {
      const sec = Number(t.duration_seconds)
      const duration = Number.isFinite(sec) ? `${sec.toFixed(2)} sec` : '—'
      return [
        `${t.label}: ${duration}`,
        `  START: ${t.start_time || '—'}`,
        `  END: ${t.end_time || '—'}`,
        `  DURATION: ${duration}`,
      ].join('\n')
    })
    const total = data.total_duration_seconds
    if (total != null && Number.isFinite(Number(total))) {
      blocks.push(`TOTAL: ${Number(total).toFixed(1)} sec`)
    }
    return blocks.join('\n\n')
  }

  const lines = buildPerformanceLines(data)
  return lines.length ? lines.join('\n') : ''
}

export function progressPercent(completed, total) {
  if (!total) return 0
  return Math.min(100, Math.round((completed / total) * 100))
}
