export const SPLASH_STATUSES = [
  'Initializing...',
  'Loading AI Pipeline...',
  'Preparing Workspace...',
]

export const PROCESSING_PHASES = [
  {
    id: 1,
    label: 'Script Generation',
    progress: 33,
    logs: [
      'Connecting to script engine...',
      '[✓] Phase 1 - Script Generation',
    ],
  },
  {
    id: 2,
    label: 'Metadata Generation',
    progress: 66,
    logs: [
      'Generating title and description...',
      '[✓] Phase 2 - Metadata Generation',
    ],
  },
  {
    id: 3,
    label: 'Voice Generation',
    progress: 100,
    logs: [
      'Synthesizing narration audio...',
      '[✓] Phase 3 - Voice Generation',
    ],
  },
]

export const RESULT_PLACEHOLDER = {
  title: 'Your Video Title Will Appear Here',
  description:
    'Your generated description will appear here — optimized for Shorts discovery, engagement hooks, and platform metadata when the pipeline is connected.',
  hashtags: ['Shorts', 'ContentCreation', 'AutoShorts', 'YouTubeTips', 'Viral'],
}
