"""SQLAlchemy ORM models for ClipDeck."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    totp_secret: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Streamer(Base):
    __tablename__ = "streamers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # twitch/kick/youtube
    platform_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    relationship_type: Mapped[str] = mapped_column(
        String(32), default="none", nullable=False
    )  # none/editor/broadcaster_authorized
    auto_monitor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    niche: Mapped[str | None] = mapped_column(String(64), nullable=True)
    keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    emote_list: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sessions: Mapped[list["StreamSession"]] = relationship(back_populates="streamer", cascade="all, delete-orphan")
    moments: Mapped[list["Moment"]] = relationship(back_populates="streamer", cascade="all, delete-orphan")
    clips: Mapped[list["Clip"]] = relationship(back_populates="streamer", cascade="all, delete-orphan")
    presets: Mapped[list["LayoutPreset"]] = relationship(back_populates="streamer", cascade="all, delete-orphan")


class StreamSession(Base):
    __tablename__ = "stream_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int] = mapped_column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="live", nullable=False)  # live/ended/error
    viewer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    platform_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    streamer: Mapped["Streamer"] = relationship(back_populates="sessions")
    chat_stats: Mapped[list["ChatStatsBucket"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    moments: Mapped[list["Moment"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatStatsBucket(Base):
    __tablename__ = "chat_stats_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stream_sessions.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    messages_per_second: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hype_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    top_emotes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    caps_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    copypasta_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    session: Mapped["StreamSession"] = relationship(back_populates="chat_stats")


class Moment(Base):
    __tablename__ = "moments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stream_sessions.id", ondelete="SET NULL"), nullable=True
    )
    streamer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False
    )
    hype_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    clip_start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    clip_end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    clip_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    chat_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chat_messages_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="detected", nullable=False
    )  # detected/clipping/clipped/error/reviewed/approved/rejected
    trigger_type: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)  # auto/manual
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    session: Mapped["StreamSession | None"] = relationship(back_populates="moments")
    streamer: Mapped["Streamer"] = relationship(back_populates="moments")
    clips: Mapped[list["Clip"]] = relationship(back_populates="moment", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue: Mapped[str] = mapped_column(String(32), nullable=False)  # ingest/detect/render/publish
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, index=True
    )  # pending/running/completed/failed/cancelled
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    streamer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("streamers.id", ondelete="SET NULL"), nullable=True
    )
    moment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("moments.id", ondelete="SET NULL"), nullable=True
    )


class ProviderKey(Base):
    __tablename__ = "provider_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_name: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Phase 2 Models: AI Editing, Playbooks, Templates, Costs
# ---------------------------------------------------------------------------


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    moment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("moments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    streamer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List[str]
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="scoring", nullable=False, index=True
    )  # scoring, editing, rendering, rendered, failed
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16", nullable=False)
    cost_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    moment: Mapped["Moment | None"] = relationship(back_populates="clips")
    streamer: Mapped["Streamer"] = relationship(back_populates="clips")
    edit_versions: Mapped[list["EditVersion"]] = relationship(back_populates="clip", cascade="all, delete-orphan")
    playbook_traces: Mapped[list["ClipPlaybookTrace"]] = relationship(back_populates="clip", cascade="all, delete-orphan")


class EditVersion(Base):
    __tablename__ = "edit_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clip_id: Mapped[int] = mapped_column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    edl_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    clip: Mapped["Clip"] = relationship(back_populates="edit_versions")


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(
        String(32), default="global", nullable=False, index=True
    )  # global/platform/streamer/category/target
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    versions: Mapped[list["PlaybookVersion"]] = relationship(back_populates="playbook", cascade="all, delete-orphan")
    files: Mapped[list["PlaybookFile"]] = relationship(back_populates="playbook", cascade="all, delete-orphan")
    examples: Mapped[list["PlaybookExample"]] = relationship(back_populates="playbook", cascade="all, delete-orphan")


class PlaybookVersion(Base):
    __tablename__ = "playbook_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    playbook: Mapped["Playbook"] = relationship(back_populates="versions")
    traces: Mapped[list["ClipPlaybookTrace"]] = relationship(back_populates="playbook_version")


class PlaybookFile(Base):
    __tablename__ = "playbook_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)  # md, txt, json
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    playbook: Mapped["Playbook"] = relationship(back_populates="files")


class PlaybookExample(Base):
    __tablename__ = "playbook_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True)
    example_type: Mapped[str] = mapped_column(String(16), default="good", nullable=False)  # good/bad
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    playbook: Mapped["Playbook"] = relationship(back_populates="examples")


class ClipPlaybookTrace(Base):
    __tablename__ = "clip_playbook_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clip_id: Mapped[int] = mapped_column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    playbook_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("playbook_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rule_violations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rules_applied: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    clip: Mapped["Clip"] = relationship(back_populates="playbook_traces")
    playbook_version: Mapped["PlaybookVersion | None"] = relationship(back_populates="traces")


class LayoutPreset(Base):
    __tablename__ = "layout_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    layout_type: Mapped[str] = mapped_column(String(64), nullable=False)  # vertical_split, cam_over_gameplay, etc.
    facecam_box: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # x, y, width, height, etc.
    gameplay_box: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # x, y, width, height, etc.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    streamer: Mapped["Streamer | None"] = relationship(back_populates="presets")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)  # scoring, edl, title
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_model: Mapped[str] = mapped_column(String(64), default="gemini-1.5-flash", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CostLedger(Base):
    __tablename__ = "cost_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audio_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
