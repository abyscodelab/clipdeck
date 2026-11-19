#!/usr/bin/env python3
"""Migrate existing SQLite ClipDeck data into Supabase PostgreSQL with type coercion.

Usage:
    python seed/migrate_to_supabase.py
"""

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.config import settings
from app.database import engine, Base, init_db, async_session
import app.models  # ensure models are loaded

BOOL_COLUMNS = {
    "totp_enabled",
    "must_change_password",
    "auto_monitor",
    "enabled",
    "is_default",
}

DATETIME_COLUMNS = {
    "created_at",
    "updated_at",
    "started_at",
    "ended_at",
    "detected_at",
    "completed_at",
    "timestamp",
}

JSON_COLUMNS = {
    "keywords",
    "emote_list",
    "config",
    "top_emotes",
    "signals",
    "chat_data",
    "chat_messages_snapshot",
    "params",
    "result",
    "value",
    "hashtags",
    "edl_data",
    "rule_violations",
    "rules_applied",
    "facecam_box",
    "gameplay_box",
}


def coerce_value(key: str, val):
    if val is None:
        return None
    if key in BOOL_COLUMNS:
        return bool(val)
    if key in DATETIME_COLUMNS and isinstance(val, str):
        try:
            # Handle ISO format
            clean_str = val.replace("Z", "+00:00")
            return datetime.fromisoformat(clean_str)
        except Exception:
            try:
                return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return val
    if key in JSON_COLUMNS and isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


async def migrate_data(sqlite_path: str):
    """Read data from SQLite and copy into the target PostgreSQL database."""
    print(f"Connecting to target database: {settings.DATABASE_URL}")

    await init_db()
    print("Database tables verified.")

    if not os.path.exists(sqlite_path):
        print(f"SQLite file not found at {sqlite_path}.")
        return

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [
        "users",
        "streamers",
        "stream_sessions",
        "chat_stats_buckets",
        "moments",
        "jobs",
        "provider_keys",
        "settings",
        "clips",
        "edit_versions",
        "playbooks",
        "playbook_versions",
        "playbook_files",
        "playbook_examples",
        "clip_playbook_traces",
        "layout_presets",
        "prompt_templates",
        "cost_ledger",
    ]

    async with async_session() as session:
        for table in tables:
            try:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                if not rows:
                    continue

                cols = rows[0].keys()
                col_names = ", ".join(cols)
                placeholders = ", ".join([f":{c}" for c in cols])

                stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")
                
                success_count = 0
                for row in rows:
                    data = {k: coerce_value(k, row[k]) for k in cols}
                    try:
                        await session.execute(stmt, data)
                        success_count += 1
                    except Exception as e:
                        # Row might already exist or conflict
                        pass

                await session.commit()
                print(f"Migrated {success_count}/{len(rows)} records for {table}.")

                # Reset Postgres sequence if id exists
                if "id" in cols:
                    try:
                        seq_name = f"{table}_id_seq"
                        await session.execute(text(f"SELECT setval('{seq_name}', (SELECT COALESCE(MAX(id), 1) FROM {table}))"))
                        await session.commit()
                    except Exception:
                        pass

            except sqlite3.OperationalError:
                continue
            except Exception as e:
                print(f"Warning while migrating {table}: {e}")
                await session.rollback()

    conn.close()
    print("Migration finished cleanly!")


def main():
    parser = argparse.ArgumentParser(description="Migrate ClipDeck data to Supabase")
    parser.add_argument(
        "--sqlite",
        default="clipdeck.db" if os.path.exists("clipdeck.db") else "data/clipdeck.db",
        help="Path to SQLite database",
    )
    args = parser.parse_args()
    asyncio.run(migrate_data(args.sqlite))


if __name__ == "__main__":
    main()
