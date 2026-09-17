PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS julia_workers (
    worker_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    worker_class TEXT NOT NULL,
    authorization_state TEXT NOT NULL CHECK (
        authorization_state IN ('AUTHORIZED', 'UNAUTHORIZED', 'DISABLED')
    ),
    availability_state TEXT NOT NULL CHECK (
        availability_state IN (
            'AVAILABLE', 'DEGRADED', 'RATE_LIMITED', 'QUOTA_EXHAUSTED',
            'AUTH_REQUIRED', 'PROVIDER_UNAVAILABLE', 'TOOL_UNAVAILABLE',
            'DISABLED', 'UNKNOWN'
        )
    ),
    privacy_class TEXT NOT NULL CHECK (
        privacy_class IN ('LOCAL_ONLY', 'REPOSITORY_ONLY', 'PRIVATE_CLOUD', 'PUBLIC_CLOUD')
    ),
    descriptor_json TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS julia_routing_decisions (
    decision_id TEXT PRIMARY KEY,
    objective_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_category TEXT NOT NULL,
    selected_worker_id TEXT,
    decision_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_julia_decisions_task
    ON julia_routing_decisions(task_id, created_at_ms);

CREATE TABLE IF NOT EXISTS julia_worker_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objective_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_category TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    failure_type TEXT CHECK (
        failure_type IS NULL OR failure_type IN (
            'WORKER_FAILURE', 'RATE_LIMITED', 'QUOTA_EXHAUSTED', 'AUTH_FAILURE',
            'PROVIDER_UNAVAILABLE', 'TOOL_FAILURE', 'TIMEOUT', 'CONTEXT_LIMIT',
            'BUDGET_EXCEEDED', 'VERIFICATION_FAILURE', 'POLICY_BLOCK', 'UNKNOWN'
        )
    ),
    final_status TEXT NOT NULL,
    outcome_json TEXT NOT NULL,
    recorded_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_julia_outcomes_worker_category
    ON julia_worker_outcomes(worker_id, task_category, recorded_at_ms);
