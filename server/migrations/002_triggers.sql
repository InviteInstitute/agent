-- Behavior triggers the check-in daemon detected, each kept once: a trigger at a run index
-- fires once per session. The inactive trigger fires at -1, and each re-alert of a student who
-- stays idle steps the index down (-2, -3, ...), so the same key dedupes those too.

CREATE TABLE triggers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    environment TEXT NOT NULL,
    student_key TEXT NOT NULL,
    session_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    run_index INTEGER NOT NULL,
    detail JSONB,
    fired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- An inactive trigger closes when the student acts again.
    resolved_at TIMESTAMPTZ,
    -- The check-in the agent sent for it, if it sent one.
    message_id BIGINT REFERENCES messages (id) ON DELETE SET NULL,
    UNIQUE (environment, student_key, session_id, trigger_type, run_index)
);

CREATE INDEX triggers_student ON triggers (environment, student_key, session_id, trigger_type, fired_at);
