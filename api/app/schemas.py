"""Pydantic request/response schemas for the ClipDeck API (Phase 1 & Phase 2)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_base64: str


class TOTPVerifyRequest(BaseModel):
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    totp_enabled: bool
    must_change_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Streamer
# ---------------------------------------------------------------------------

class StreamerCreate(BaseModel):
    name: str
    platform: str = Field(pattern=r"^(twitch|kick|youtube)$")
    platform_id: str | None = None
    url: str | None = None
    relationship_type: str = Field(default="none", pattern=r"^(none|editor|broadcaster_authorized)$")
    auto_monitor: bool = False
    priority: int = 0
    niche: str | None = None
    keywords: list[str] | None = None
    emote_list: list[str] | None = None
    notes: str | None = None
    config: dict[str, Any] | None = None


class StreamerUpdate(BaseModel):
    name: str | None = None
    platform: str | None = Field(default=None, pattern=r"^(twitch|kick|youtube)$")
    platform_id: str | None = None
    url: str | None = None
    relationship_type: str | None = Field(default=None, pattern=r"^(none|editor|broadcaster_authorized)$")
    auto_monitor: bool | None = None
    priority: int | None = None
    niche: str | None = None
    keywords: list[str] | None = None
    emote_list: list[str] | None = None
    notes: str | None = None
    config: dict[str, Any] | None = None


class StreamerResponse(BaseModel):
    id: int
    name: str
    platform: str
    platform_id: str | None
    url: str | None
    relationship_type: str
    auto_monitor: bool
    priority: int
    niche: str | None
    keywords: list[str] | None
    emote_list: list[str] | None
    notes: str | None
    config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stream Session
# ---------------------------------------------------------------------------

class StreamSessionResponse(BaseModel):
    id: int
    streamer_id: int
    started_at: datetime
    ended_at: datetime | None
    status: str
    viewer_count: int | None
    platform_session_id: str | None

    model_config = {"from_attributes": True}


class ChatStatsBucketResponse(BaseModel):
    id: int
    session_id: int
    timestamp: datetime
    messages_per_second: float
    hype_score: float
    top_emotes: dict[str, Any] | None
    signals: dict[str, Any] | None
    caps_ratio: float
    copypasta_ratio: float

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Moment
# ---------------------------------------------------------------------------

class MomentResponse(BaseModel):
    id: int
    session_id: int | None
    streamer_id: int
    hype_score: float
    detected_at: datetime
    clip_start_time: float | None
    clip_end_time: float | None
    clip_duration: float | None
    file_path: str | None
    thumbnail_path: str | None
    chat_data: dict[str, Any] | None
    chat_messages_snapshot: dict[str, Any] | None
    status: str
    trigger_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MomentStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(detected|clipping|clipped|error|reviewed|approved|rejected)$")


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

class JobResponse(BaseModel):
    id: int
    queue: str
    job_type: str
    status: str
    params: dict[str, Any] | None
    result: dict[str, Any] | None
    error: str | None
    retries: int
    max_retries: int
    progress: float
    log: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    streamer_id: int | None
    moment_id: int | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Settings & Provider Keys
# ---------------------------------------------------------------------------

class SettingResponse(BaseModel):
    id: int
    key: str
    value: Any
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingsUpdateRequest(BaseModel):
    settings: dict[str, Any]


class ProviderKeyCreate(BaseModel):
    provider: str
    key_name: str
    value: str  # plaintext, will be encrypted before storage


class ProviderKeyUpdate(BaseModel):
    value: str


class ProviderKeyResponse(BaseModel):
    id: int
    provider: str
    key_name: str
    masked_value: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Health & SSE
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str = "0.2.0"
    database: str
    disk_usage: dict[str, Any] | None = None


class SSEEvent(BaseModel):
    event: str  # hype_update, new_moment, job_update, streamer_status, system_alert, clip_rendered
    data: dict[str, Any]


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


# ===========================================================================
# Phase 2 Schemas: AI Editing & Playbooks
# ===========================================================================

# ---------------------------------------------------------------------------
# EDL (Edit Decision List) Schema
# ---------------------------------------------------------------------------

class EDLCut(BaseModel):
    start: float = Field(description="Segment in-point seconds relative to raw clip")
    end: float = Field(description="Segment out-point seconds relative to raw clip")
    speed: float = Field(default=1.0, description="Playback speed multiplier")


class EDLOverlay(BaseModel):
    overlay_type: str = Field(description="Type of overlay: subtitle, text_hook, sound_effect, watermark")
    content: str = Field(description="Text content, image path, or SFX identifier")
    start: float
    end: float
    position: dict[str, Any] | None = Field(default=None, description="Coordinates / layout styling")


class EDLLayout(BaseModel):
    layout_preset_id: int | None = None
    layout_type: str = Field(default="vertical_split", description="e.g. vertical_split, cam_over_gameplay, full_vertical")
    facecam_box: dict[str, Any] | None = None
    gameplay_box: dict[str, Any] | None = None


class EDLData(BaseModel):
    cuts: list[EDLCut] = Field(default_factory=list)
    overlays: list[EDLOverlay] = Field(default_factory=list)
    layout: EDLLayout | None = None
    audio_gain: float = 1.0
    music_track: str | None = None


# ---------------------------------------------------------------------------
# Moment Scoring & AI Reasoning
# ---------------------------------------------------------------------------

class MomentScoreRequest(BaseModel):
    moment_id: int
    streamer_id: int
    transcript: str | None = None
    chat_summary: dict[str, Any] | None = None


class MomentScoreResult(BaseModel):
    moment_id: int
    viral_score: float = Field(ge=0.0, le=100.0, description="Overall virality index")
    hook_strength: float = Field(ge=0.0, le=10.0)
    punchline_clarity: float = Field(ge=0.0, le=10.0)
    reasoning: str
    suggested_title: str
    suggested_tags: list[str] = Field(default_factory=list)
    target_aspect_ratio: str = "9:16"


# ---------------------------------------------------------------------------
# Clips & Edit Versions
# ---------------------------------------------------------------------------

class EditVersionCreate(BaseModel):
    clip_id: int
    edl_data: dict[str, Any]
    ai_reasoning: str | None = None
    model_used: str | None = None


class EditVersionResponse(BaseModel):
    id: int
    clip_id: int
    version_number: int
    edl_data: dict[str, Any] | None
    ai_reasoning: str | None
    model_used: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipPlaybookTraceResponse(BaseModel):
    id: int
    clip_id: int
    playbook_version_id: int | None
    rule_violations: list[str] | None
    rules_applied: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipCreate(BaseModel):
    moment_id: int | None = None
    streamer_id: int
    title: str
    description: str | None = None
    hashtags: list[str] | None = None
    duration: float = 0.0
    status: str = Field(default="scoring", pattern=r"^(scoring|editing|rendering|rendered|failed)$")
    aspect_ratio: str = "9:16"
    edl_data: dict[str, Any] | None = None
    ai_reasoning: str | None = None
    model_used: str | None = None


class ClipUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    status: str | None = Field(default=None, pattern=r"^(scoring|editing|rendering|rendered|failed)$")
    aspect_ratio: str | None = None
    duration: float | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None


class ClipRerenderRequest(BaseModel):
    layout_preset_id: int | None = None
    edl_data: dict[str, Any] | None = None
    aspect_ratio: str | None = None


class ClipResponse(BaseModel):
    id: int
    moment_id: int | None
    streamer_id: int
    title: str
    description: str | None
    hashtags: list[str] | None
    duration: float
    status: str
    file_path: str | None
    thumbnail_path: str | None
    aspect_ratio: str
    cost_tokens: int
    cost_usd: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClipDetailResponse(ClipResponse):
    edit_versions: list[EditVersionResponse] = Field(default_factory=list)
    playbook_traces: list[ClipPlaybookTraceResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Playbooks, Versions, Files, Examples
# ---------------------------------------------------------------------------

class PlaybookCreate(BaseModel):
    name: str
    description: str | None = None
    scope: str = Field(default="global", pattern=r"^(global|platform|streamer|category|target)$")
    target_id: str | None = None
    priority: int = 0
    enabled: bool = True
    content: str


class PlaybookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: str | None = Field(default=None, pattern=r"^(global|platform|streamer|category|target)$")
    target_id: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    content: str | None = None
    change_summary: str | None = "Updated playbook content"


class PlaybookVersionResponse(BaseModel):
    id: int
    playbook_id: int
    version_number: int
    content: str
    change_summary: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookFileResponse(BaseModel):
    id: int
    playbook_id: int
    filename: str
    file_type: str
    extracted_text: str
    original_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookExampleCreate(BaseModel):
    example_type: str = Field(default="good", pattern=r"^(good|bad)$")
    url: str | None = None
    notes: str | None = None
    transcript: str | None = None


class PlaybookExampleResponse(BaseModel):
    id: int
    playbook_id: int
    example_type: str
    url: str | None
    notes: str | None
    transcript: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookResponse(BaseModel):
    id: int
    name: str
    description: str | None
    scope: str
    target_id: str | None
    priority: int
    enabled: bool
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlaybookDetailResponse(PlaybookResponse):
    versions: list[PlaybookVersionResponse] = Field(default_factory=list)
    files: list[PlaybookFileResponse] = Field(default_factory=list)
    examples: list[PlaybookExampleResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Playbook Test Bench
# ---------------------------------------------------------------------------

class PlaybookTestBenchRequest(BaseModel):
    sample_transcript: str
    metadata: dict[str, Any] | None = None
    streamer_id: int | None = None


class PlaybookTestBenchResponse(BaseModel):
    evaluated_playbooks: int
    rules_applied: list[str]
    rule_violations: list[str]
    passes_hard_rules: bool
    recommendations: list[str]


# ---------------------------------------------------------------------------
# Layout Preset
# ---------------------------------------------------------------------------

class LayoutPresetCreate(BaseModel):
    streamer_id: int | None = None
    name: str
    layout_type: str
    facecam_box: dict[str, Any] | None = None
    gameplay_box: dict[str, Any] | None = None
    is_default: bool = False


class LayoutPresetUpdate(BaseModel):
    streamer_id: int | None = None
    name: str | None = None
    layout_type: str | None = None
    facecam_box: dict[str, Any] | None = None
    gameplay_box: dict[str, Any] | None = None
    is_default: bool | None = None


class LayoutPresetResponse(BaseModel):
    id: int
    streamer_id: int | None
    name: str
    layout_type: str
    facecam_box: dict[str, Any] | None
    gameplay_box: dict[str, Any] | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Prompt Template
# ---------------------------------------------------------------------------

class PromptTemplateCreate(BaseModel):
    task_type: str = Field(pattern=r"^(scoring|edl|title)$")
    template_text: str
    system_prompt: str | None = None
    default_model: str = "gemini-1.5-flash"


class PromptTemplateUpdate(BaseModel):
    template_text: str | None = None
    system_prompt: str | None = None
    default_model: str | None = None


class PromptTemplateResponse(BaseModel):
    id: int
    task_type: str
    template_text: str
    system_prompt: str | None
    default_model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Cost Ledger & Spend Summary
# ---------------------------------------------------------------------------

class CostLedgerCreate(BaseModel):
    job_type: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    audio_seconds: float = 0.0
    cost_usd: float = 0.0


class CostLedgerResponse(BaseModel):
    id: int
    timestamp: datetime
    job_type: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    audio_seconds: float
    cost_usd: float

    model_config = {"from_attributes": True}


class CostSummaryResponse(BaseModel):
    daily_spend_usd: float
    monthly_spend_usd: float
    total_spend_usd: float
    daily_token_count: int
    monthly_token_count: int
    total_token_count: int
    spend_cap_usd: float
    cap_reached: bool
    breakdown_by_provider: dict[str, float]
    breakdown_by_job_type: dict[str, float]
