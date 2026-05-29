CREATE TABLE IF NOT EXISTS discovery_sessions (
    id              TEXT PRIMARY KEY,
    product_type    TEXT NOT NULL,
    initial_description TEXT NOT NULL,
    state_json      TEXT NOT NULL,
    history_json    TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('in_progress', 'complete', 'abandoned')),
    rounds_used     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON discovery_sessions(status);

CREATE TABLE IF NOT EXISTS validation_reports (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES discovery_sessions(id),
    spec_json       TEXT NOT NULL,
    image_paths_json TEXT NOT NULL,
    conform_json     TEXT NOT NULL,
    neconform_json   TEXT NOT NULL,
    nevizibil_json   TEXT NOT NULL,
    raw_llm_response TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS match_sessions (
    id                  TEXT PRIMARY KEY,
    sim_image_path      TEXT NOT NULL,
    real_image_path     TEXT,
    sim_report_json     TEXT NOT NULL,
    compare_report_json TEXT,
    status              TEXT NOT NULL
                        CHECK (status IN ('awaiting_real', 'complete', 'failed')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_match_status
    ON match_sessions(status);
