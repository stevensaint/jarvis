PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS julia_runtime_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    snapshot_json TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS julia_runtime_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN (
            'STARTING', 'RUNNING', 'DEGRADED', 'PAUSED', 'STOPPING',
            'STOPPED', 'RECOVERING', 'FAILED'
        )
    ),
    node_id TEXT,
    detail TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS julia_nodes (
    node_id TEXT PRIMARY KEY,
    availability_state TEXT NOT NULL CHECK (
        availability_state IN (
            'ONLINE', 'DEGRADED', 'BUSY', 'PAUSED', 'DRAINING',
            'OFFLINE', 'UNKNOWN'
        )
    ),
    is_primary INTEGER NOT NULL CHECK (is_primary IN (0, 1)),
    descriptor_json TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_julia_one_primary_node
    ON julia_nodes(is_primary) WHERE is_primary = 1;

CREATE TABLE IF NOT EXISTS julia_execution_attempts (
    attempt_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    objective_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    node_id TEXT,
    worker_id TEXT,
    state TEXT NOT NULL CHECK (
        state IN (
            'PLANNED', 'RUNNING', 'AWAITING_VERIFICATION',
            'AWAITING_APPROVAL', 'SUCCEEDED', 'FAILED', 'CANCELLED',
            'INTERRUPTED'
        )
    ),
    side_effect_state TEXT NOT NULL CHECK (
        side_effect_state IN ('NONE', 'IDEMPOTENT', 'COMMITTED', 'UNKNOWN')
    ),
    attempt_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_julia_attempts_objective
    ON julia_execution_attempts(objective_id, task_id, updated_at_ms);

CREATE TABLE IF NOT EXISTS julia_recovery_records (
    recovery_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    objective_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (
        disposition IN (
            'RESUME', 'RETRY', 'REPLAN', 'VERIFY', 'AWAIT_APPROVAL',
            'MANUAL_RECONCILIATION', 'CANCEL'
        )
    ),
    recovery_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    FOREIGN KEY(attempt_id) REFERENCES julia_execution_attempts(attempt_id)
);

CREATE INDEX IF NOT EXISTS idx_julia_recovery_objective
    ON julia_recovery_records(objective_id, created_at_ms);
