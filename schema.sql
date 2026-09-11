CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    identifier TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL CHECK (type IN ('team', 'player')),
    name TEXT,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS snapshots (
    id BIGSERIAL PRIMARY KEY,
    identifier TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('team', 'player')),
    races BIGINT DEFAULT 0,
    accuracy NUMERIC(5,2) DEFAULT 0.00,
    wpm NUMERIC(5,1) DEFAULT 0.0,
    points BIGINT DEFAULT 0,
    ppr NUMERIC(6,2) DEFAULT 0.00,
    online_status BOOLEAN DEFAULT FALSE,
    membership_status TEXT DEFAULT 'basic',
    car_img_url TEXT DEFAULT '',
    title TEXT DEFAULT '',
    team_tag TEXT DEFAULT '',
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ident_cap ON snapshots(identifier, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_type_cap ON snapshots(type, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_entities_lookup ON entities(identifier, type);
