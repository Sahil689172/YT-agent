import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
} from 'react'
import {
  generateFromTopic,
  generateFromScript,
  getProgress,
  getResult,
  ApiError,
} from '../lib/api'
import { sanitizeScript } from '../utils/sanitizeScript'

const GenerationContext = createContext(null)

const initialState = {
  jobId: null,
  mode: null, // 'topic' | 'script'
  progress: null,
  result: null,
  loading: false,
  error: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'RESET':
      return { ...initialState }
    case 'SET_LOADING':
      return { ...state, loading: action.payload, error: null }
    case 'SET_JOB':
      return {
        ...state,
        jobId: action.payload.jobId,
        mode: action.payload.mode,
        loading: false,
        error: null,
        progress: null,
        result: null,
      }
    case 'SET_PROGRESS':
      return { ...state, progress: action.payload, error: null }
    case 'SET_RESULT': {
      const payload = action.payload
      const progress = state.progress
      const merged = { ...payload }
      if (progress) {
        if (!merged.phase_timings?.length && progress.phase_timings?.length) {
          merged.phase_timings = progress.phase_timings
        }
        if (!merged.performance_summary?.length && progress.performance_summary?.length) {
          merged.performance_summary = progress.performance_summary
        }
        if (merged.total_duration_seconds == null && progress.total_duration_seconds != null) {
          merged.total_duration_seconds = progress.total_duration_seconds
        }
      }
      return {
        ...state,
        result: merged,
        progress,
        loading: false,
        error: null,
      }
    }
    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false }
    default:
      return state
  }
}

export function GenerationProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const clearJob = useCallback(() => {
    dispatch({ type: 'RESET' })
  }, [])

  const startTopic = useCallback(async (topic) => {
    const trimmed = topic?.trim()
    if (!trimmed) {
      throw new ApiError('Invalid Input', 'Please enter a topic.')
    }
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      const data = await generateFromTopic(trimmed)
      dispatch({
        type: 'SET_JOB',
        payload: { jobId: data.job_id, mode: 'topic' },
      })
      return data.job_id
    } catch (err) {
      const error =
        err instanceof ApiError
          ? err
          : new ApiError('Generation Failed', err?.message || 'Unknown error')
      dispatch({ type: 'SET_ERROR', payload: error })
      throw error
    }
  }, [])

  const startScript = useCallback(async (rawScript, topicLabel = 'Custom Script') => {
    const sanitized = sanitizeScript(rawScript)
    if (!sanitized) {
      throw new ApiError(
        'Invalid Script',
        'Your script is empty after cleanup. Paste narration text only.',
      )
    }
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      const data = await generateFromScript(sanitized, topicLabel)
      dispatch({
        type: 'SET_JOB',
        payload: { jobId: data.job_id, mode: 'script' },
      })
      return data.job_id
    } catch (err) {
      const error =
        err instanceof ApiError
          ? err
          : new ApiError('Generation Failed', err?.message || 'Unknown error')
      dispatch({ type: 'SET_ERROR', payload: error })
      throw error
    }
  }, [])

  const refreshProgress = useCallback(async (jobId) => {
    const data = await getProgress(jobId)
    dispatch({ type: 'SET_PROGRESS', payload: data })
    return data
  }, [])

  const fetchAndStoreResult = useCallback(async (jobId) => {
    const data = await getResult(jobId)
    if (data.status === 'failed') {
      throw new ApiError(
        'Video Creation Failed',
        data.error || 'Pipeline failed.',
      )
    }
    dispatch({ type: 'SET_RESULT', payload: data })
    return data
  }, [])

  const value = useMemo(
    () => ({
      ...state,
      startTopic,
      startScript,
      refreshProgress,
      fetchAndStoreResult,
      clearJob,
    }),
    [
      state,
      startTopic,
      startScript,
      refreshProgress,
      fetchAndStoreResult,
      clearJob,
    ],
  )

  return (
    <GenerationContext.Provider value={value}>
      {children}
    </GenerationContext.Provider>
  )
}

export function useGeneration() {
  const ctx = useContext(GenerationContext)
  if (!ctx) {
    throw new Error('useGeneration must be used within GenerationProvider')
  }
  return ctx
}
