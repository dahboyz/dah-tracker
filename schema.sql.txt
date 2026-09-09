-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table 1: Tracked Entities (Teams and Racers)
CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    identifier TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL CHECK (type IN ('team', 'player')),
    name TEXT,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table 2: Historical Stat Snapshots
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

-- High-Performance Indexes for Instant High-Speed Delta Queries
CREATE INDEX IF NOT EXISTS idx_snapshots_ident_cap ON snapshots(identifier, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_type_cap ON snapshots(type, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_entities_lookup ON entities(identifier, type);

-- Seed Data: 30 Popular Nitro Type Team Tags
INSERT INTO entities (identifier, type, name) VALUES
('nt', 'team', 'NT'),
('tbz', 'team', 'TBZ'),
('wealth', 'team', 'WEALTH'),
('e10', 'team', 'E10'),
('ssh', 'team', 'SSH'),
('bn8', 'team', 'BN8'),
('ntc', 'team', 'NTC'),
('tche', 'team', 'TCHE'),
('dhbz', 'team', 'DHBZ'),
('dsnt', 'team', 'DSNT'),
('ldt', 'team', 'LDT'),
('rcws', 'team', 'RCWS'),
('topgod', 'team', 'TOPGOD'),
('nts', 'team', 'NTS'),
('flpr', 'team', 'FLPR'),
('emz', 'team', 'EMZ'),
('beehve', 'team', 'BEEHVE'),
('n8te', 'team', 'N8TE'),
('rnl', 'team', 'RNL'),
('tpx', 'team', 'TPX'),
('s0rc', 'team', 'S0RC'),
('knc', 'team', 'KNC'),
('hyt', 'team', 'HYT'),
('stpr', 'team', 'STPR'),
('ktty', 'team', 'KTTY'),
('mwy', 'team', 'MWY'),
('rrr1', 'team', 'RRR1'),
('ntpd1', 'team', 'NTPD1'),
('sbd', 'team', 'SBD'),
('xpl', 'team', 'XPL')
ON CONFLICT (identifier) DO NOTHING;

-- Seed Data: 30 Top Nitro Type Players
INSERT INTO entities (identifier, type, name) VALUES
('wildflower', 'player', 'Wildflower'),
('travis', 'player', 'Travis'),
('shooter', 'player', 'Shooter'),
('speeddemon', 'player', 'Speed Demon'),
('ninja', 'player', 'NinjaTyper'),
('pracer', 'player', 'Pro Racer'),
('hypertyper', 'player', 'Hyper Typer'),
('lightning', 'player', 'Lightning Bolt'),
('nitroking', 'player', 'Nitro King'),
('dashm', 'player', 'Dash Master'),
('racerx', 'player', 'Racer X'),
('storm', 'player', 'Storm Chaser'),
('phantom', 'player', 'Phantom Typer'),
('vortex', 'player', 'Vortex Racer'),
('blaze', 'player', 'Blaze'),
('shadow', 'player', 'Shadow Runner'),
('apex_legend', 'player', 'Apex Legend'),
('turbo', 'player', 'Turbo Charger'),
('starlight', 'player', 'Starlight'),
('swift', 'player', 'Swift Keys'),
('overdrive', 'player', 'Overdrive'),
('comet', 'player', 'Comet Typer'),
('pulse', 'player', 'Pulse Racer'),
('velocity', 'player', 'Velocity'),
('ace_typer', 'player', 'Ace Typer'),
('zenith', 'player', 'Zenith'),
('titan', 'player', 'Titan Typer'),
('spectre', 'player', 'Spectre'),
('cyclone', 'player', 'Cyclone'),
('fury', 'player', 'Fury Racer')
ON CONFLICT (identifier) DO NOTHING;