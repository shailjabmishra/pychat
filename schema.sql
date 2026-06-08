CREATE TABLE IF NOT EXISTS messages (
    id          SERIAL PRIMARY KEY,
    sender      VARCHAR(64)  NOT NULL,
    content     TEXT         NOT NULL,
    sent_at     TIMESTAMPTZ  DEFAULT NOW(),
    is_direct   BOOLEAN      DEFAULT FALSE,
    recipient   VARCHAR(64)  -- NULL for broadcast, username for DMs
);
CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at DESC);