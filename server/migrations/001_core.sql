-- Everything the agent keeps: the students' learner logs from each environment, how far each
-- log source has been read, the chat, ratings of replies, LLM spending and research settings.
--
-- A student is (environment, student_key). Each environment makes the key from what the
-- student signs in with (see agent/environments): VEXcode VR folds the student ID's case,
-- ZANY joins the class code and the student ID, so S01 in two classes stays two students.

CREATE TABLE events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    environment TEXT NOT NULL,
    -- The record's own id in its source (an Invite Hub log id, an ATLAS seq), so a record
    -- read twice is kept once.
    source_id TEXT NOT NULL,
    student_key TEXT NOT NULL,
    student_id TEXT NOT NULL,
    class_code TEXT,
    session_id TEXT NOT NULL,
    event_ts TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ,
    event_type TEXT NOT NULL,
    -- The playground's name in its environment's catalog, or as logged when it has none.
    playground TEXT,
    project JSONB,
    block_event JSONB,
    playground_data JSONB,
    error_message TEXT,
    UNIQUE (environment, source_id)
);

CREATE INDEX events_student ON events (environment, student_key, session_id, event_ts);
CREATE INDEX events_latest ON events (environment, student_key, event_ts DESC);
CREATE INDEX events_recent ON events (environment, event_ts);

-- Where to resume reading each source. `position` is the source's own resume point.
CREATE TABLE ingest_cursors (
    source TEXT PRIMARY KEY,
    position JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    environment TEXT NOT NULL,
    student_key TEXT NOT NULL,
    session_id TEXT NOT NULL,
    -- A researcher's chat stays apart from what students see, so an experiment never
    -- becomes the history of a student's reply. Check-ins are kept in the student chat
    -- and read into both.
    chat TEXT NOT NULL CHECK (chat IN ('student', 'research')),
    role TEXT NOT NULL CHECK (role IN ('student', 'agent')),
    origin TEXT NOT NULL CHECK (origin IN ('reactive', 'proactive')),
    body TEXT NOT NULL,
    -- The id a client rates an agent reply by.
    response_id UUID UNIQUE,
    question_type TEXT,
    feedback_classes TEXT[],
    trigger_type TEXT,
    -- What the agent saw and did for this reply: the situation, the model, the prompt,
    -- the settings and the tokens, so research can read why it said what it said.
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX messages_chat ON messages (environment, student_key, session_id, id);
CREATE INDEX messages_proactive ON messages (environment, student_key, id) WHERE origin = 'proactive';

CREATE TABLE ratings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
    thumb TEXT NOT NULL CHECK (thumb IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ratings_message ON ratings (message_id);

-- One row per LLM call made for a browser, so a browser session and the whole site each
-- have a token ceiling. budget_key hashes the browser's Turnstile cookie.
CREATE TABLE llm_usage (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    budget_key TEXT NOT NULL,
    environment TEXT,
    student_key TEXT,
    model TEXT NOT NULL,
    origin TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX llm_usage_budget ON llm_usage (budget_key, created_at);
CREATE INDEX llm_usage_created ON llm_usage (created_at);

-- The agent settings a researcher picked for a student, so check-ins, which no request
-- carries, follow them too. No row means production.
CREATE TABLE agent_settings (
    environment TEXT NOT NULL,
    student_key TEXT NOT NULL,
    settings JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (environment, student_key)
);
