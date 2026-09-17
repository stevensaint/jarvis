// Julia Sprint 1 worker-routing wire vocabulary. Keep in parity with
// jarvis/julia/routing/contracts.py and routing/schema.sql.
export const AVAILABILITY_STATES = [
  'AVAILABLE',
  'DEGRADED',
  'RATE_LIMITED',
  'QUOTA_EXHAUSTED',
  'AUTH_REQUIRED',
  'PROVIDER_UNAVAILABLE',
  'TOOL_UNAVAILABLE',
  'DISABLED',
  'UNKNOWN',
] as const

export type AvailabilityState = (typeof AVAILABILITY_STATES)[number]

export const FAILURE_TYPES = [
  'WORKER_FAILURE',
  'RATE_LIMITED',
  'QUOTA_EXHAUSTED',
  'AUTH_FAILURE',
  'PROVIDER_UNAVAILABLE',
  'TOOL_FAILURE',
  'TIMEOUT',
  'CONTEXT_LIMIT',
  'BUDGET_EXCEEDED',
  'VERIFICATION_FAILURE',
  'POLICY_BLOCK',
  'UNKNOWN',
] as const

export type WorkerFailureType = (typeof FAILURE_TYPES)[number]

export const PRIVACY_CLASSES = [
  'LOCAL_ONLY',
  'REPOSITORY_ONLY',
  'PRIVATE_CLOUD',
  'PUBLIC_CLOUD',
] as const

export type WorkerPrivacyClass = (typeof PRIVACY_CLASSES)[number]

export interface CandidateEvaluation {
  worker_id: string
  eligible: boolean
  rejection_reasons: string[]
  score: number | null
  score_components: Record<string, number>
}

export const NODE_AVAILABILITY_STATES = [
  'ONLINE',
  'DEGRADED',
  'BUSY',
  'PAUSED',
  'DRAINING',
  'OFFLINE',
  'UNKNOWN',
] as const

export type NodeAvailabilityState = (typeof NODE_AVAILABILITY_STATES)[number]
