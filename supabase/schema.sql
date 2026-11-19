-- =============================================================================
-- ClipDeck v2.0 - Complete Supabase PostgreSQL Schema
-- Run this script in the Supabase SQL Editor (Dashboard > SQL Editor > New Query)
-- =============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. TABLES

-- Users & Authentication
CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    totp_secret BYTEA,
    totp_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    must_change_password BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Streamers
CREATE TABLE IF NOT EXISTS public.streamers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    platform VARCHAR(32) NOT NULL, -- twitch / kick / youtube
    platform_id VARCHAR(128),
    url VARCHAR(512),
    relationship_type VARCHAR(32) DEFAULT 'none' NOT NULL, -- none / editor / broadcaster_authorized
    auto_monitor BOOLEAN DEFAULT FALSE NOT NULL,
    priority INT DEFAULT 0 NOT NULL,
    niche VARCHAR(64),
    keywords JSONB,
    emote_list JSONB,
    notes TEXT,
    config JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_streamers_name ON public.streamers(name);
CREATE INDEX IF NOT EXISTS idx_streamers_platform ON public.streamers(platform);

-- Stream Sessions
CREATE TABLE IF NOT EXISTS public.stream_sessions (
    id SERIAL PRIMARY KEY,
    streamer_id INT NOT NULL REFERENCES public.streamers(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(16) DEFAULT 'live' NOT NULL, -- live / ended / error
    viewer_count INT,
    platform_session_id VARCHAR(128)
);
CREATE INDEX IF NOT EXISTS idx_sessions_streamer ON public.stream_sessions(streamer_id);

-- Chat Stats Buckets (Realtime Hype Tracking)
CREATE TABLE IF NOT EXISTS public.chat_stats_buckets (
    id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES public.stream_sessions(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    messages_per_second FLOAT DEFAULT 0.0 NOT NULL,
    hype_score FLOAT DEFAULT 0.0 NOT NULL,
    top_emotes JSONB,
    signals JSONB,
    caps_ratio FLOAT DEFAULT 0.0 NOT NULL,
    copypasta_ratio FLOAT DEFAULT 0.0 NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_stats_session ON public.chat_stats_buckets(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_stats_timestamp ON public.chat_stats_buckets(timestamp);

-- Detected Moments
CREATE TABLE IF NOT EXISTS public.moments (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES public.stream_sessions(id) ON DELETE SET NULL,
    streamer_id INT NOT NULL REFERENCES public.streamers(id) ON DELETE CASCADE,
    hype_score FLOAT DEFAULT 0.0 NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    clip_start_time FLOAT,
    clip_end_time FLOAT,
    clip_duration FLOAT,
    file_path VARCHAR(512),
    thumbnail_path VARCHAR(512),
    chat_data JSONB,
    chat_messages_snapshot JSONB,
    status VARCHAR(16) DEFAULT 'detected' NOT NULL, -- detected/clipping/clipped/error/reviewed/approved/rejected
    trigger_type VARCHAR(16) DEFAULT 'auto' NOT NULL, -- auto / manual
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_moments_streamer ON public.moments(streamer_id);
CREATE INDEX IF NOT EXISTS idx_moments_detected_at ON public.moments(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_moments_status ON public.moments(status);

-- Worker Jobs
CREATE TABLE IF NOT EXISTS public.jobs (
    id SERIAL PRIMARY KEY,
    queue VARCHAR(32) NOT NULL, -- ingest / detect / render / publish
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(16) DEFAULT 'pending' NOT NULL, -- pending/running/completed/failed/cancelled
    params JSONB,
    result JSONB,
    error TEXT,
    retries INT DEFAULT 0 NOT NULL,
    max_retries INT DEFAULT 3 NOT NULL,
    progress FLOAT DEFAULT 0.0 NOT NULL,
    log TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    streamer_id INT REFERENCES public.streamers(id) ON DELETE SET NULL,
    moment_id INT REFERENCES public.moments(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON public.jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_queue ON public.jobs(queue);

-- Provider Keys (Encrypted)
CREATE TABLE IF NOT EXISTS public.provider_keys (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    key_name VARCHAR(64) NOT NULL,
    encrypted_value BYTEA NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_keys_provider ON public.provider_keys(provider);

-- System Settings
CREATE TABLE IF NOT EXISTS public.settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(128) UNIQUE NOT NULL,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Clips (Vertical 9:16 Video Projects)
CREATE TABLE IF NOT EXISTS public.clips (
    id SERIAL PRIMARY KEY,
    moment_id INT REFERENCES public.moments(id) ON DELETE SET NULL,
    streamer_id INT NOT NULL REFERENCES public.streamers(id) ON DELETE CASCADE,
    title VARCHAR(256) NOT NULL,
    description TEXT,
    hashtags JSONB,
    duration FLOAT DEFAULT 0.0 NOT NULL,
    status VARCHAR(32) DEFAULT 'scoring' NOT NULL, -- scoring/editing/rendering/rendered/failed
    file_path VARCHAR(512),
    thumbnail_path VARCHAR(512),
    aspect_ratio VARCHAR(16) DEFAULT '9:16' NOT NULL,
    cost_tokens INT DEFAULT 0 NOT NULL,
    cost_usd FLOAT DEFAULT 0.0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clips_status ON public.clips(status);
CREATE INDEX IF NOT EXISTS idx_clips_streamer ON public.clips(streamer_id);

-- Edit Versions (AI EDL and Reasoning)
CREATE TABLE IF NOT EXISTS public.edit_versions (
    id SERIAL PRIMARY KEY,
    clip_id INT NOT NULL REFERENCES public.clips(id) ON DELETE CASCADE,
    version_number INT DEFAULT 1 NOT NULL,
    edl_data JSONB,
    ai_reasoning TEXT,
    model_used VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edit_versions_clip ON public.edit_versions(clip_id);

-- Playbooks (AI Editing Rulesets)
CREATE TABLE IF NOT EXISTS public.playbooks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    scope VARCHAR(32) DEFAULT 'global' NOT NULL, -- global/platform/streamer/category/target
    target_id VARCHAR(128),
    priority INT DEFAULT 0 NOT NULL,
    enabled BOOLEAN DEFAULT TRUE NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_playbooks_scope ON public.playbooks(scope);

-- Playbook Versions
CREATE TABLE IF NOT EXISTS public.playbook_versions (
    id SERIAL PRIMARY KEY,
    playbook_id INT NOT NULL REFERENCES public.playbooks(id) ON DELETE CASCADE,
    version_number INT DEFAULT 1 NOT NULL,
    content TEXT NOT NULL,
    change_summary VARCHAR(256),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_playbook_versions_parent ON public.playbook_versions(playbook_id);

-- Playbook Supporting Files
CREATE TABLE IF NOT EXISTS public.playbook_files (
    id SERIAL PRIMARY KEY,
    playbook_id INT NOT NULL REFERENCES public.playbooks(id) ON DELETE CASCADE,
    filename VARCHAR(256) NOT NULL,
    file_type VARCHAR(32) NOT NULL,
    extracted_text TEXT NOT NULL,
    original_path VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Playbook Examples (Few-Shot Context)
CREATE TABLE IF NOT EXISTS public.playbook_examples (
    id SERIAL PRIMARY KEY,
    playbook_id INT NOT NULL REFERENCES public.playbooks(id) ON DELETE CASCADE,
    example_type VARCHAR(16) DEFAULT 'good' NOT NULL, -- good / bad
    url VARCHAR(512),
    notes TEXT,
    transcript TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Clip Playbook Traces
CREATE TABLE IF NOT EXISTS public.clip_playbook_traces (
    id SERIAL PRIMARY KEY,
    clip_id INT NOT NULL REFERENCES public.clips(id) ON DELETE CASCADE,
    playbook_version_id INT REFERENCES public.playbook_versions(id) ON DELETE SET NULL,
    rule_violations JSONB,
    rules_applied JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Layout Presets
CREATE TABLE IF NOT EXISTS public.layout_presets (
    id SERIAL PRIMARY KEY,
    streamer_id INT REFERENCES public.streamers(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    layout_type VARCHAR(64) NOT NULL,
    facecam_box JSONB,
    gameplay_box JSONB,
    is_default BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Prompt Templates
CREATE TABLE IF NOT EXISTS public.prompt_templates (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(32) UNIQUE NOT NULL, -- scoring / edl / title
    template_text TEXT NOT NULL,
    system_prompt TEXT,
    default_model VARCHAR(64) DEFAULT 'gemini-1.5-flash' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Cost Ledger
CREATE TABLE IF NOT EXISTS public.cost_ledger (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    job_type VARCHAR(64) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model VARCHAR(64) NOT NULL,
    input_tokens INT DEFAULT 0 NOT NULL,
    output_tokens INT DEFAULT 0 NOT NULL,
    audio_seconds FLOAT DEFAULT 0.0 NOT NULL,
    cost_usd FLOAT DEFAULT 0.0 NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cost_ledger_timestamp ON public.cost_ledger(timestamp DESC);

-- 3. STORAGE BUCKETS (Public CDN for Clips & Thumbnails)
INSERT INTO storage.buckets (id, name, public)
VALUES 
    ('clips', 'clips', true),
    ('thumbnails', 'thumbnails', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Storage Policies (Allow public reads and service-role/authenticated uploads)
DO $$
BEGIN
    -- Public Read access
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Public Access for Thumbnails') THEN
        CREATE POLICY "Public Access for Thumbnails" ON storage.objects FOR SELECT USING (bucket_id = 'thumbnails');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Public Access for Clips') THEN
        CREATE POLICY "Public Access for Clips" ON storage.objects FOR SELECT USING (bucket_id = 'clips');
    END IF;
    -- Write access for service role and authenticated
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow Uploads for Thumbnails') THEN
        CREATE POLICY "Allow Uploads for Thumbnails" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'thumbnails');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow Uploads for Clips') THEN
        CREATE POLICY "Allow Uploads for Clips" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'clips');
    END IF;
END $$;

-- 4. REALTIME REPLICATION (Broadcast changes instantly to Web UI)
ALTER PUBLICATION supabase_realtime ADD TABLE public.moments;
ALTER PUBLICATION supabase_realtime ADD TABLE public.clips;
ALTER PUBLICATION supabase_realtime ADD TABLE public.stream_sessions;
ALTER PUBLICATION supabase_realtime ADD TABLE public.jobs;

-- 5. INITIAL SEED DATA

-- Default Admin User (Password: changeme)
-- bcrypt hash of 'changeme'
INSERT INTO public.users (id, username, password_hash, must_change_password)
VALUES (
    1,
    'admin',
    '$2b$12$KIXeW9V331L32P76oYmKbe6kH12X1x6Yt0t/e9f.H8E5aXJpG9a2S',
    false
)
ON CONFLICT (username) DO NOTHING;

-- Default Prompt Templates
INSERT INTO public.prompt_templates (task_type, default_model, template_text, system_prompt)
VALUES 
(
    'scoring',
    'gemini-1.5-flash',
    'Analyze the following streamer moment transcript and chat metrics to produce a virality score (0-100), key hook line, and emotional sentiment:\n\nStreamer: {streamer_name}\nHype Velocity: {mps} mps\nPeak Score: {peak_score}\nTranscript:\n{transcript}',
    'You are an expert social media clipping director specializing in TikTok, Instagram Reels, and YouTube Shorts pacing.'
),
(
    'edl',
    'gemini-1.5-flash',
    'Generate an edit decision list (EDL) in 9:16 vertical format for this segment. Apply kinetic punch cuts, zooms on reaction beats, and hook subtitle styling.\n\nPlaybook Rules:\n{playbook_rules}\n\nTranscript with timestamps:\n{timestamps_transcript}',
    'You are a high-retention video editor creating viral 9:16 vertical short-form clips.'
),
(
    'title',
    'gemini-1.5-flash',
    'Write 3 viral, high-CTR titles and 5 trending hashtags for this vertical video:\n{summary}',
    'You write viral YouTube Shorts and TikTok hooks without cheesy AI buzzwords.'
)
ON CONFLICT (task_type) DO NOTHING;

-- Default Playbooks
INSERT INTO public.playbooks (name, description, scope, content)
VALUES 
(
    'Viral Gaming Highlights',
    'High retention rules for fast-paced gaming clutch moments and hype reactions.',
    'global',
    '# Viral Gaming Highlights Playbook\n\n## Hook Strategy\n- First 2 seconds must show the climax or scream sound bite before cutting back.\n- Use heavy bold subtitle animations on the trigger phrase.\n\n## Visuals\n- Split view: 35% Facecam top, 65% Gameplay bottom.\n- Punch zoom 1.2x on clutch headshots or failed plays.'
),
(
    'IRL & Just Chatting',
    'Storytelling and drama framing for conversational streamers.',
    'global',
    '# IRL & Conversational Playbook\n\n## Hook Strategy\n- Start directly in the middle of the argument or shocking statement.\n- Emphasize subtitles with yellow keyword callouts.'
)
ON CONFLICT DO NOTHING;

-- Reset sequence IDs
SELECT setval('public.users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public.users));
SELECT setval('public.streamers_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public.streamers));
SELECT setval('public.moments_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public.moments));
SELECT setval('public.clips_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public.clips));
SELECT setval('public.playbooks_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public.playbooks));
