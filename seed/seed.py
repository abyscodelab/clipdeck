#!/usr/bin/env python3
"""ClipDeck Seed, Replay, and Phase 2 AI Pipeline Runner

Seeds initial demo data (DemoStreamer, StreamSession, Moments, and Starter Playbooks)
into SQLite by feeding synthetic chat logs (seed/demo_chat.jsonl) through the HypeDetector.
Also provides a full Phase 2 `--pipeline` mode that simulates transcription, AI scoring,
EDL generation, and executes a deterministic FFmpeg 9:16 vertical render (seed/test_clip.mp4).

Usage:
    python -m seed.seed                 # Standard seed & moment detection
    python -m seed.seed --replay        # Interactive live chat replay simulation
    python -m seed.seed --pipeline      # Run Phase 2 AI editing & FFmpeg render pipeline
    python -m seed.seed --speed 5.0     # Adjust replay playback speed
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# Setup paths so imports work whether run from project root, seed dir, or inside container
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT.parent))

# Setup aliases if necessary
try:
    import clipdeck.shared.detection.hype_detector as _hd_test  # noqa: F401
except ImportError:
    try:
        import shared
        import types
        clipdeck_mod = types.ModuleType("clipdeck")
        clipdeck_mod.shared = shared
        sys.modules["clipdeck"] = clipdeck_mod
        sys.modules["clipdeck.shared"] = shared
    except ImportError:
        pass

from clipdeck.shared.detection.hype_detector import HypeDetector
from clipdeck.shared.detection.signals import DetectorConfig
from clipdeck.shared.platforms.base import ChatMessage

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")


def get_db_path(cli_path: str | None = None) -> Path:
    """Determine SQLite database file path from CLI, env, or defaults."""
    if cli_path:
        p = Path(cli_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    env_url = os.environ.get("DATABASE_URL", "")
    for prefix in ["sqlite+aiosqlite:///", "sqlite:///"]:
        if env_url.startswith(prefix):
            raw_path = env_url.replace(prefix, "")
            p = Path(raw_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            return p

    # Standard default locations
    for candidate in [
        Path("/data/clipdeck.db"),
        PROJECT_ROOT / "data" / "clipdeck.db",
        PROJECT_ROOT / "clipdeck.db",
    ]:
        if candidate.parent.exists():
            return candidate

    default_path = PROJECT_ROOT / "data" / "clipdeck.db"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    return default_path


def init_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Ensure all required Phase 1 and Phase 2 tables exist in SQLite."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            totp_secret BLOB,
            totp_enabled BOOLEAN NOT NULL DEFAULT 0,
            must_change_password BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS streamers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(128) NOT NULL,
            platform VARCHAR(32) NOT NULL,
            platform_id VARCHAR(128),
            url VARCHAR(512),
            relationship_type VARCHAR(32) NOT NULL DEFAULT 'none',
            auto_monitor BOOLEAN NOT NULL DEFAULT 0,
            priority INTEGER NOT NULL DEFAULT 0,
            niche VARCHAR(64),
            keywords JSON,
            emote_list JSON,
            notes TEXT,
            config JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stream_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME,
            status VARCHAR(16) NOT NULL DEFAULT 'live',
            viewer_count INTEGER,
            platform_session_id VARCHAR(128)
        );

        CREATE TABLE IF NOT EXISTS chat_stats_buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES stream_sessions(id) ON DELETE CASCADE,
            timestamp DATETIME NOT NULL,
            messages_per_second FLOAT NOT NULL DEFAULT 0.0,
            hype_score FLOAT NOT NULL DEFAULT 0.0,
            top_emotes JSON,
            signals JSON,
            caps_ratio FLOAT NOT NULL DEFAULT 0.0,
            copypasta_ratio FLOAT NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS moments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES stream_sessions(id) ON DELETE SET NULL,
            streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
            hype_score FLOAT NOT NULL DEFAULT 0.0,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            clip_start_time FLOAT,
            clip_end_time FLOAT,
            clip_duration FLOAT,
            file_path VARCHAR(512),
            thumbnail_path VARCHAR(512),
            chat_data JSON,
            chat_messages_snapshot JSON,
            status VARCHAR(16) NOT NULL DEFAULT 'detected',
            trigger_type VARCHAR(16) NOT NULL DEFAULT 'auto',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue VARCHAR(32) NOT NULL,
            job_type VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            params JSON,
            result JSON,
            error TEXT,
            retries INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            progress FLOAT NOT NULL DEFAULT 0.0,
            log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            streamer_id INTEGER REFERENCES streamers(id) ON DELETE SET NULL,
            moment_id INTEGER REFERENCES moments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key VARCHAR(128) UNIQUE NOT NULL,
            value JSON NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS provider_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR(64) NOT NULL,
            key_name VARCHAR(128) NOT NULL,
            encrypted_value BLOB NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Phase 2 Tables: Playbooks, Clips, Layouts, Templates, Costs
        CREATE TABLE IF NOT EXISTS playbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(128) NOT NULL,
            description TEXT,
            scope VARCHAR(32) NOT NULL DEFAULT 'global',
            target_id VARCHAR(128),
            priority INTEGER NOT NULL DEFAULT 0,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS playbook_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id INTEGER NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL DEFAULT 1,
            content TEXT NOT NULL,
            change_summary VARCHAR(256),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS playbook_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id INTEGER NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE,
            filename VARCHAR(256) NOT NULL,
            file_path VARCHAR(512) NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            mime_type VARCHAR(64) NOT NULL DEFAULT 'text/plain',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS playbook_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id INTEGER NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE,
            title VARCHAR(256) NOT NULL,
            notes TEXT,
            video_path VARCHAR(512),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS clip_playbook_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
            playbook_version_id INTEGER NOT NULL REFERENCES playbook_versions(id) ON DELETE CASCADE,
            applied_rules JSON,
            passed_checks BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moment_id INTEGER REFERENCES moments(id) ON DELETE SET NULL,
            streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
            title VARCHAR(256) NOT NULL,
            description TEXT,
            hashtags JSON,
            duration FLOAT NOT NULL DEFAULT 0.0,
            status VARCHAR(32) NOT NULL DEFAULT 'scoring',
            file_path VARCHAR(512),
            thumbnail_path VARCHAR(512),
            aspect_ratio VARCHAR(16) NOT NULL DEFAULT '9:16',
            cost_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd FLOAT NOT NULL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS edit_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL DEFAULT 1,
            edl_data JSON,
            ai_reasoning TEXT,
            model_used VARCHAR(64),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS layout_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            streamer_id INTEGER REFERENCES streamers(id) ON DELETE CASCADE,
            name VARCHAR(128) NOT NULL,
            layout_type VARCHAR(64) NOT NULL,
            facecam_box JSON,
            gameplay_box JSON,
            is_default BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type VARCHAR(32) UNIQUE NOT NULL,
            template_text TEXT NOT NULL,
            system_prompt TEXT,
            default_model VARCHAR(64) NOT NULL DEFAULT 'gemini-1.5-flash',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cost_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            job_type VARCHAR(64) NOT NULL,
            provider VARCHAR(64) NOT NULL,
            model VARCHAR(64) NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            audio_seconds FLOAT DEFAULT 0.0,
            cost_usd FLOAT DEFAULT 0.0
        );
        """
    )
    conn.commit()


def seed_default_admin(conn: sqlite3.Connection) -> None:
    """Ensure default admin account exists."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        # Valid bcrypt hash for 'changeme'
        pw_hash = "$2b$12$6IXh/MSwnSYIAl17ZnH7/OpNxtXzKJjUv4xI/JsTTUBX4jaG7JIFO"
        cur.execute(
            """
            INSERT INTO users (username, password_hash, must_change_password, totp_enabled)
            VALUES (?, ?, 0, 0)
            """,
            ("admin", pw_hash),
        )
        conn.commit()
        logger.info("Created default admin user (admin / changeme).")


def seed_playbooks(conn: sqlite3.Connection) -> list[int]:
    """Bootstrap starter playbooks from seed/playbooks/ into the database."""
    cur = conn.cursor()
    playbooks_dir = SCRIPT_DIR / "playbooks"

    definitions = [
        {
            "file": "viral_moments.md",
            "name": "Viral Moments & Brand-Safe Rules",
            "scope": "global",
            "target_id": "global",
            "description": "Global default rules enforcing brand safety, hard exclusions, and core viral patterns.",
            "rules": {
                "viral_patterns": ["rage", "fails", "clutch_plays", "wholesome", "hot_takes", "collab"],
                "hard_rules": ["no_gambling", "no_minors", "no_dmca_music", "no_slurs", "no_doxxing"],
            },
            "style": {"hook_max_sec": 2.0, "dead_air_threshold": 0.7, "min_duration": 15, "max_duration": 60},
        },
        {
            "file": "gaming_clips.md",
            "name": "Gaming Highlights & Pacing",
            "scope": "category",
            "target_id": "gaming",
            "description": "Category playbook for fast-paced gaming clips, clutch plays, and rage moments.",
            "rules": {
                "viral_patterns": ["clutch", "desk_slam", "whiff", "game_glitch", "esports_take"],
                "hard_rules": ["no_loading_screens", "no_inventory_screens", "no_muted_audio", "no_toxicity"],
            },
            "style": {"hook_max_sec": 1.5, "dead_air_threshold": 0.5, "min_duration": 18, "max_duration": 45},
        },
        {
            "file": "irl_clips.md",
            "name": "IRL & Street Streaming Rules",
            "scope": "category",
            "target_id": "irl",
            "description": "Category playbook for outdoor, travel, and public interaction live streams.",
            "rules": {
                "viral_patterns": ["public_reactions", "wholesome_bystanders", "travel_fails", "street_collabs"],
                "hard_rules": ["no_doxxing", "no_unconsenting_filming", "no_minors", "no_traffic_infractions"],
            },
            "style": {"hook_max_sec": 2.0, "dead_air_threshold": 0.7, "min_duration": 20, "max_duration": 55},
        },
    ]

    playbook_ids = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for item in definitions:
        fpath = playbooks_dir / item["file"]
        content = fpath.read_text(encoding="utf-8") if fpath.exists() else f"# {item['name']}\n\nPlaceholder"

        cur.execute("SELECT id FROM playbooks WHERE name = ?", (item["name"],))
        row = cur.fetchone()
        if row:
            playbook_id = row[0]
            cur.execute(
                """
                UPDATE playbooks SET
                    content = ?, description = ?, updated_at = ?
                WHERE id = ?
                """,
                (content, item["description"], now_iso, playbook_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO playbooks (
                    name, scope, target_id, priority, enabled, description,
                    content, created_at, updated_at
                ) VALUES (?, ?, ?, 100, 1, ?, ?, ?, ?)
                """,
                (
                    item["name"],
                    item["scope"],
                    item["target_id"],
                    item["description"],
                    content,
                    now_iso,
                    now_iso,
                ),
            )
            playbook_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO playbook_versions (playbook_id, version_number, content, change_summary, created_at)
                VALUES (?, 1, ?, 'Initial seed version', ?)
                """,
                (playbook_id, content, now_iso),
            )
            logger.info("Seeded Playbook: '%s' (Scope: %s, ID: %d)", item["name"], item["scope"], playbook_id)
        playbook_ids.append(playbook_id)

    conn.commit()
    return playbook_ids


def get_or_create_streamer(conn: sqlite3.Connection) -> int:
    """Create or fetch DemoStreamer."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM streamers WHERE name = 'DemoStreamer'")
    row = cur.fetchone()
    if row:
        return row[0]

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO streamers (
            name, platform, platform_id, url, relationship_type,
            auto_monitor, priority, niche, keywords, emote_list, notes, config,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "DemoStreamer",
            "twitch",
            "demo_123456",
            "https://twitch.tv/demostreamer",
            "broadcaster_authorized",
            1,
            10,
            "gaming",
            json.dumps(["pog", "insane", "clutch", "fail", "win"]),
            json.dumps(["KEKW", "PogChamp", "FeelsGoodMan", "LUL", "pepeLaugh"]),
            "Official demo streamer seeded for testing ClipDeck hype detection.",
            json.dumps({"baseline_min_secs": 10, "hype_threshold": 50.0}),
            now_iso,
            now_iso,
        ),
    )
    conn.commit()
    streamer_id = cur.lastrowid
    logger.info("Created DemoStreamer (ID: %d)", streamer_id)
    return streamer_id


def create_stream_session(conn: sqlite3.Connection, streamer_id: int) -> int:
    """Create a new live StreamSession for demo."""
    cur = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO stream_sessions (streamer_id, started_at, status, viewer_count, platform_session_id)
        VALUES (?, ?, 'live', 14200, ?)
        """,
        (streamer_id, now_iso, f"session_seed_{int(time.time())}"),
    )
    conn.commit()
    session_id = cur.lastrowid
    logger.info("Created StreamSession (ID: %d) for streamer %d", session_id, streamer_id)
    return session_id


def load_chat_log(chat_file: Path) -> list[dict]:
    """Load JSONL chat log."""
    if not chat_file.exists():
        raise FileNotFoundError(f"Chat log not found: {chat_file}")
    messages = []
    with open(chat_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                messages.append(json.loads(line))
    return messages


def run_seed_and_detection(
    db_path: Path,
    chat_file: Path,
    replay: bool = False,
    speed: float = 1.0,
) -> tuple[int, int, list[int]]:
    """Execute hype detection on pre-recorded chat log and write results to SQLite."""
    logger.info("Connecting to database at: %s", db_path)
    conn = sqlite3.connect(str(db_path))

    init_sqlite_schema(conn)
    seed_default_admin(conn)
    seed_playbooks(conn)
    streamer_id = get_or_create_streamer(conn)
    session_id = create_stream_session(conn, streamer_id)

    raw_messages = load_chat_log(chat_file)
    logger.info("Loaded %d chat messages from %s", len(raw_messages), chat_file)

    # Initialize HypeDetector with demo-friendly warmup
    config = DetectorConfig(
        baseline_min_secs=10,
        hype_threshold=50.0,
        cooldown_secs=15.0,
        clip_pre_secs=30.0,
        clip_post_secs=10.0,
    )
    detector = HypeDetector(streamer_id=streamer_id, config=config)

    # Group messages into 1-second time windows
    t_base = raw_messages[0]["timestamp"]
    buckets: dict[int, list[ChatMessage]] = {}
    for m in raw_messages:
        sec = int(m["timestamp"] - t_base)
        buckets.setdefault(sec, []).append(
            ChatMessage(
                text=m["text"],
                username=m["username"],
                timestamp=m["timestamp"],
                is_sub=m.get("is_sub", False),
                bits=m.get("bits", 0),
            )
        )

    max_sec = max(buckets.keys())
    cur = conn.cursor()

    logger.info("Starting detection over %d simulated seconds (replay=%s, speed=%.1fx)...", max_sec + 1, replay, speed)

    detected_moments = []
    moment_ids = []
    stats_count = 0

    for sec in range(max_sec + 1):
        sec_msgs = buckets.get(sec, [])
        simulated_ts = t_base + sec

        # Feed messages to detector
        detector.feed_messages(sec_msgs, simulated_ts)
        score_info = detector.get_current_score()
        stats_bucket = detector.get_stats_bucket()

        # Persist stats bucket to SQLite
        if stats_bucket:
            now_dt = datetime.datetime.fromtimestamp(simulated_ts, datetime.timezone.utc).isoformat()
            cur.execute(
                """
                INSERT INTO chat_stats_buckets (
                    session_id, timestamp, messages_per_second, hype_score,
                    top_emotes, signals, caps_ratio, copypasta_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    now_dt,
                    stats_bucket.messages_per_second,
                    stats_bucket.hype_score,
                    json.dumps(stats_bucket.top_emotes),
                    json.dumps(stats_bucket.signals),
                    stats_bucket.caps_ratio,
                    stats_bucket.copypasta_ratio,
                ),
            )
            stats_count += 1

        # Check for moment trigger
        if score_info.triggered_moment:
            m_trigger = score_info.triggered_moment
            duration = max(5.0, m_trigger.end_time - m_trigger.start_time)
            moment_dt = datetime.datetime.fromtimestamp(m_trigger.peak_time, datetime.timezone.utc).isoformat()
            moment_idx = len(detected_moments) + 1

            cur.execute(
                """
                INSERT INTO moments (
                    session_id, streamer_id, hype_score, detected_at,
                    clip_start_time, clip_end_time, clip_duration,
                    file_path, thumbnail_path, chat_data, chat_messages_snapshot,
                    status, trigger_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'detected', 'auto')
                """,
                (
                    session_id,
                    streamer_id,
                    m_trigger.peak_score,
                    moment_dt,
                    m_trigger.start_time,
                    m_trigger.end_time,
                    duration,
                    f"/data/media/clips/demo_moment_{moment_idx}.mp4",
                    f"/data/media/thumbnails/demo_moment_{moment_idx}.jpg",
                    json.dumps(m_trigger.signals_at_peak),
                    json.dumps(m_trigger.top_messages),
                ),
            )
            moment_id = cur.lastrowid
            detected_moments.append(m_trigger)
            moment_ids.append(moment_id)

            logger.info(
                "🔥 MOMENT TRIGGERED #%d (ID: %d) at sec %d | Peak Score: %.1f | Clip window: %.1f - %.1f (%.1fs)",
                moment_idx,
                moment_id,
                sec,
                m_trigger.peak_score,
                m_trigger.start_time,
                m_trigger.end_time,
                duration,
            )

        # Visual display in replay mode
        if replay:
            score_bar = "█" * int(score_info.score / 5)
            sys.stdout.write(
                f"\r[T+{sec:03d}s] Score: {score_info.score:5.1f} | MPS: {score_info.signals.get('messages_per_second', 0.0):4.1f} | {score_bar:<20} "
            )
            sys.stdout.flush()
            if speed > 0:
                time.sleep(1.0 / (20.0 * speed))

    if replay:
        print()

    conn.commit()
    conn.close()

    logger.info("=" * 60)
    logger.info("SEED & DETECTION COMPLETE")
    logger.info("Database: %s", db_path)
    logger.info("Streamer ID: %d (DemoStreamer)", streamer_id)
    logger.info("Session ID: %d", session_id)
    logger.info("Stats buckets stored: %d", stats_count)
    logger.info("Moments detected: %d (IDs: %s)", len(detected_moments), moment_ids)
    logger.info("=" * 60)

    return streamer_id, session_id, moment_ids


def run_phase2_pipeline(
    db_path: Path,
    moment_id: int | None = None,
) -> Path:
    """Execute Phase 2 AI Pipeline simulation:

    1. Selects or fetches a detected Moment.
    2. Attaches word-level transcript.
    3. Runs AI scoring & rule checks against active Playbooks.
    4. Generates an Edit Decision List (EDL) with blurred_bg layout.
    5. Executes deterministic FFmpeg to render 1080x1920 seed/test_clip.mp4.
    6. Saves Clip record to the database.
    """
    logger.info("🎬 Starting Phase 2 AI Editing & Render Pipeline Simulation...")
    conn = sqlite3.connect(str(db_path))
    init_sqlite_schema(conn)
    seed_default_admin(conn)
    seed_playbooks(conn)
    cur = conn.cursor()

    # Find target moment
    if moment_id:
        cur.execute("SELECT id, streamer_id, hype_score, chat_messages_snapshot FROM moments WHERE id = ?", (moment_id,))
    else:
        cur.execute("SELECT id, streamer_id, hype_score, chat_messages_snapshot FROM moments ORDER BY hype_score DESC LIMIT 1")

    row = cur.fetchone()
    if not row:
        logger.warning("No moment found in DB. Seeding initial detection first...")
        s_id, _, m_ids = run_seed_and_detection(db_path, SCRIPT_DIR / "demo_chat.jsonl")
        cur.execute("SELECT id, streamer_id, hype_score, chat_messages_snapshot FROM moments WHERE id = ?", (m_ids[0],))
        row = cur.fetchone()

    m_id, s_id, hype_score, chat_snapshot_json = row
    chat_snapshot = json.loads(chat_snapshot_json) if chat_snapshot_json else []

    logger.info("Target Moment ID: %d | Streamer ID: %d | Hype Score: %.1f", m_id, s_id, hype_score)

    # 1. Generate Word-Level Transcript (Deepgram/Whisper simulation)
    transcript_data = {
        "text": "Wait what was that? No shot he just hit that 360 no scope across the map! Holy cow clip that right now!",
        "words": [
            {"word": "Wait", "start": 0.0, "end": 0.35, "confidence": 0.98},
            {"word": "what", "start": 0.35, "end": 0.65, "confidence": 0.99},
            {"word": "was", "start": 0.65, "end": 0.95, "confidence": 0.99},
            {"word": "that?", "start": 0.95, "end": 1.35, "confidence": 0.97},
            {"word": "No", "start": 1.55, "end": 1.85, "confidence": 0.99},
            {"word": "shot", "start": 1.85, "end": 2.15, "confidence": 0.99},
            {"word": "he", "start": 2.15, "end": 2.35, "confidence": 0.98},
            {"word": "just", "start": 2.35, "end": 2.65, "confidence": 0.99},
            {"word": "hit", "start": 2.65, "end": 2.95, "confidence": 0.99},
            {"word": "that", "start": 2.95, "end": 3.25, "confidence": 0.98},
            {"word": "360", "start": 3.35, "end": 3.75, "confidence": 0.96},
            {"word": "no", "start": 3.75, "end": 3.95, "confidence": 0.99},
            {"word": "scope", "start": 3.95, "end": 4.35, "confidence": 0.99},
            {"word": "across", "start": 4.45, "end": 4.75, "confidence": 0.98},
            {"word": "the", "start": 4.75, "end": 4.95, "confidence": 0.99},
            {"word": "map!", "start": 4.95, "end": 5.35, "confidence": 0.97},
            {"word": "Holy", "start": 5.55, "end": 5.85, "confidence": 0.99},
            {"word": "cow", "start": 5.85, "end": 6.25, "confidence": 0.98},
            {"word": "clip", "start": 6.45, "end": 6.75, "confidence": 0.99},
            {"word": "that", "start": 6.75, "end": 6.95, "confidence": 0.99},
            {"word": "right", "start": 6.95, "end": 7.25, "confidence": 0.99},
            {"word": "now!", "start": 7.25, "end": 7.75, "confidence": 0.98},
        ],
    }

    # 2. AI Moment Scoring & Playbook Alignment
    ai_score_result = {
        "ai_score": 94.5,
        "virality_tier": "S",
        "category": "Gaming Clutch Play / Impossible Trickshot",
        "hook_rating": 9.5,
        "narrative_clarity": 9.2,
        "rule_compliance": {
            "passed": True,
            "checked_rules": ["no_dmca_music", "no_loading_screens", "no_toxicity", "no_doxxing"],
            "violations": [],
        },
        "reasoning": (
            "Extreme chat velocity surge coinciding with a 360 no-scope trickshot. "
            "Strong vocal hook in the first 1.3 seconds ('Wait what was that?'). "
            "Perfect pacing for TikTok / YouTube Shorts."
        ),
    }

    # 3. Generate EDL (Edit Decision List)
    edl = {
        "version": "1.0",
        "source": "clipdeck-ai-editor-v2",
        "target_resolution": {"width": 1080, "height": 1920},
        "fps": 30,
        "layout": {
            "type": "blurred_bg",
            "bg_blur_sigma": 25,
            "bg_brightness": -0.15,
            "bg_contrast": 0.9,
            "fg_scale": 1.0,
        },
        "cuts": [
            {"cut_id": 1, "start": 0.0, "end": 7.5, "type": "content"},
        ],
        "hook_text": {
            "text": "NO SHOT HE HIT THIS 🎯",
            "start": 0.0,
            "end": 2.5,
            "style": "Hook",
        },
        "zoom_punches": [
            {"time": 3.35, "scale": 1.25, "duration": 0.6, "target": "center"},
        ],
        "captions": {
            "style": "bold_pop",
            "font": "Arial",
            "font_size": 58,
            "primary_color": "&H00FFFFFF",
            "highlight_color": "&H0000FFFF",
            "outline_color": "&H00000000",
            "outline_width": 4,
            "margin_v": 240,
        },
    }

    platform_meta = {
        "title": "HE ACTUALLY HIT THAT 360 NO SCOPE?! 🎯🔥",
        "description": "Watch @DemoStreamer pull off the impossible shot live on stream! #gaming #twitchclips #clutch #clipdeck",
        "hashtags": ["#gaming", "#twitchclips", "#clutch", "#noscope", "#clipdeck", "#viral"],
        "recommended_platforms": ["tiktok", "youtube_shorts", "instagram_reels"],
    }

    # 4. Generate ASS Subtitle File
    ass_path = SCRIPT_DIR / "test_clip.ass"
    ass_content = f"""[Script Info]
Title: ClipDeck AI Generated Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{edl['captions']['font_size']},{edl['captions']['primary_color']},&H000000FF,{edl['captions']['outline_color']},&H80000000,-1,0,0,0,100,100,0,0,1,{edl['captions']['outline_width']},2,2,40,40,{edl['captions']['margin_v']},1
Style: Hook,Arial,82,{edl['captions']['highlight_color']},&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,5,3,2,40,40,1450,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.50,Hook,,0,0,0,,{{\\b1}}{edl['hook_text']['text']}{{\\b0}}
Dialogue: 0,0:00:00.00,0:00:01.35,Default,,0,0,0,,{{\\c{edl['captions']['highlight_color']}&}}Wait{{\\c}} what was that?
Dialogue: 0,0:00:01.35,0:00:03.25,Default,,0,0,0,,No shot he {{\\c{edl['captions']['highlight_color']}&}}just hit that{{\\c}}
Dialogue: 0,0:00:03.25,0:00:05.35,Default,,0,0,0,,{{\\c&H00FF00&}}360 NO SCOPE{{\\c}} across the map!
Dialogue: 0,0:00:05.35,0:00:07.50,Default,,0,0,0,,HOLY COW {{\\c{edl['captions']['highlight_color']}&}}CLIP THAT RIGHT NOW!{{\\c}}
"""
    ass_path.write_text(ass_content, encoding="utf-8")
    logger.info("Generated ASS Subtitle Script: %s", ass_path)

    # 5. Deterministic FFmpeg Render
    output_mp4 = SCRIPT_DIR / "test_clip.mp4"
    thumb_path = SCRIPT_DIR / "test_clip.jpg"

    filter_complex = (
        "[0:v]split=2[fg_raw][bg_raw];"
        "[bg_raw]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,eq=brightness=-0.15:contrast=0.9[bg];"
        "[fg_raw]scale=1080:-1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black@0[fg];"
        "[bg][fg]overlay=0:0[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=7.5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=7.5",
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        str(output_mp4),
    ]

    logger.info("Rendering 1080x1920 9:16 vertical video via FFmpeg...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("FFmpeg render failed: %s", res.stderr[-500:])
        raise RuntimeError("FFmpeg rendering failed")

    # Generate vertical GTA VI-style thumbnail from rendered clip
    thumb_cmd = [
        "ffmpeg", "-y",
        "-ss", "00:00:02.0",
        "-i", str(output_mp4),
        "-vframes", "1",
        "-q:v", "2",
        str(thumb_path),
    ]
    subprocess.run(thumb_cmd, capture_output=True)

    try:
        from shared.media.gta_vertical_thumbnail import build_vertical_thumbnail
        build_vertical_thumbnail(
            out_path=thumb_path,
            word1="360",
            word2="NOSCOPE",
            hero_image=thumb_path if thumb_path.exists() else None,
            mode="cinematic",
            badge_title="GTA VI",
            badge_sub="CLIPPED",
        )
        logger.info("Generated GTA VI 1080x1920 vertical thumbnail: %s", thumb_path)
    except Exception as e:
        logger.warning("GTA vertical thumbnail generation failed in seed: %s", e)

    file_size_kb = output_mp4.stat().st_size / 1024
    logger.info("Rendered Clip Success: %s (%.1f KB, 1080x1920, 7.5s)", output_mp4, file_size_kb)

    # 6. Save Clip Record in Database
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO clips (
            moment_id, streamer_id, title, description, hashtags,
            duration, status, file_path, thumbnail_path, aspect_ratio,
            cost_tokens, cost_usd, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 7.5, 'rendered', ?, ?, '9:16', 350, 0.0125, ?, ?)
        """,
        (
            m_id,
            s_id,
            platform_meta["title"],
            platform_meta["description"],
            json.dumps(platform_meta["hashtags"]),
            str(output_mp4),
            str(thumb_path),
            now_iso,
            now_iso,
        ),
    )
    clip_id = cur.lastrowid

    # 7. Save initial EditVersion
    cur.execute(
        """
        INSERT INTO edit_versions (
            clip_id, version_number, edl_data, ai_reasoning, model_used, created_at
        ) VALUES (?, 1, ?, ?, 'gemini-1.5-flash', ?)
        """,
        (
            clip_id,
            json.dumps(edl),
            "Automated high-energy 9:16 crop with centered facecam and active gameplay tracking.",
            now_iso,
        ),
    )
    conn.commit()
    conn.close()

    logger.info("=" * 60)
    logger.info("PHASE 2 PIPELINE SIMULATION COMPLETE")
    logger.info("Clip ID in DB: %d", clip_id)
    logger.info("AI Virality Score: %.1f/100 (Tier: %s)", ai_score_result["ai_score"], ai_score_result["virality_tier"])
    logger.info("Title Hook: %s", platform_meta["title"])
    logger.info("Video Output: %s", output_mp4)
    logger.info("Subtitle Track: %s", ass_path)
    logger.info("Thumbnail: %s", thumb_path)
    logger.info("=" * 60)

    return output_mp4


def main() -> None:
    parser = argparse.ArgumentParser(description="ClipDeck demo seed, replay, and Phase 2 AI pipeline runner")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Simulate chat playback with live terminal metrics",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Execute Phase 2 AI scoring, EDL generation, and FFmpeg 9:16 vertical video rendering",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier in replay mode (default: 1.0)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Custom SQLite database file path",
    )
    parser.add_argument(
        "--chat-file",
        type=str,
        default=str(SCRIPT_DIR / "demo_chat.jsonl"),
        help="Path to JSONL chat log (default: seed/demo_chat.jsonl)",
    )

    args = parser.parse_args()
    db_path = get_db_path(args.db_path)
    chat_path = Path(args.chat_file).resolve()

    if args.pipeline:
        run_phase2_pipeline(db_path=db_path)
    else:
        run_seed_and_detection(
            db_path=db_path,
            chat_file=chat_path,
            replay=args.replay,
            speed=args.speed,
        )


if __name__ == "__main__":
    main()
