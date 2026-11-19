/**
 * ClipDeck TypeScript Type Definitions
 * Matches FastAPI backend schemas in app/schemas.py (Phase 1 & Phase 2)
 */

export type Platform = 'twitch' | 'kick' | 'youtube';
export type RelationshipType = 'none' | 'editor' | 'broadcaster_authorized';
export type SessionStatus = 'live' | 'ended' | 'error';
export type MomentStatus = 'detected' | 'clipping' | 'clipped' | 'error' | 'reviewed' | 'approved' | 'rejected';
export type TriggerType = 'auto' | 'manual';
export type JobQueue = 'ingest' | 'detect' | 'render' | 'publish';
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ClipStatus = 'scoring' | 'editing' | 'rendering' | 'rendered' | 'failed';
export type PlaybookScope = 'global' | 'platform' | 'streamer' | 'category' | 'target';

export interface User {
  id: number;
  username: string;
  totp_enabled: boolean;
  must_change_password: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  must_change_password: boolean;
}

export interface TOTPSetupResponse {
  secret: string;
  provisioning_uri: string;
  qr_code_base64: string;
}

export interface Streamer {
  id: number;
  name: string;
  platform: Platform;
  platform_id?: string | null;
  url?: string | null;
  relationship_type: RelationshipType;
  auto_monitor: boolean;
  priority: number;
  niche?: string | null;
  keywords?: string[] | null;
  emote_list?: string[] | null;
  notes?: string | null;
  config?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  // Dynamic client-side live state:
  is_live?: boolean;
  viewer_count?: number;
  current_hype?: number;
  current_mps?: number;
  active_session_id?: number | null;
  last_live?: string | null;
}

export interface StreamerCreate {
  name: string;
  platform: Platform;
  platform_id?: string;
  url?: string;
  relationship_type?: RelationshipType;
  auto_monitor?: boolean;
  priority?: number;
  niche?: string;
  keywords?: string[];
  emote_list?: string[];
  notes?: string;
  config?: Record<string, any>;
}

export interface StreamSession {
  id: number;
  streamer_id: number;
  started_at: string;
  ended_at?: string | null;
  status: SessionStatus;
  viewer_count?: number | null;
  platform_session_id?: string | null;
}

export interface ChatStatsBucket {
  id: number;
  session_id: number;
  timestamp: string;
  messages_per_second: number;
  hype_score: number;
  top_emotes?: Record<string, number> | null;
  signals?: Record<string, number> | null;
  caps_ratio: number;
  copypasta_ratio: number;
}

export interface Moment {
  id: number;
  session_id?: number | null;
  streamer_id: number;
  hype_score: number;
  detected_at: string;
  clip_start_time?: number | null;
  clip_end_time?: number | null;
  clip_duration?: number | null;
  file_path?: string | null;
  thumbnail_path?: string | null;
  chat_data?: Record<string, any> | null;
  chat_messages_snapshot?: Record<string, any> | null;
  status: MomentStatus;
  trigger_type: TriggerType;
  created_at: string;
  streamer?: Streamer;
  ai_score?: MomentScoreResult | null;
  latest_edl?: EditDecisionList | null;
  clips?: Clip[];
}

// ---------------------------------------------------------------------------
// Phase 2: AI Editing, Playbooks, EDL, and Clips
// ---------------------------------------------------------------------------

export interface CutSegment {
  start: number;
  end: number;
  reason?: string;
}

export interface ZoomPunch {
  timestamp: number;
  scale: number;
  duration: number;
}

export interface CaptionConfig {
  enabled: boolean;
  style?: 'pop' | 'highlight' | 'subtle' | 'clean';
  font_size?: number;
  highlight_color?: string;
}

export interface EditDecisionList {
  trim_in: number;
  trim_out: number;
  cuts?: CutSegment[];
  layout: 'blurred_bg' | 'facecam_split' | 'face_track' | 'crop_9_16';
  hook_text?: string;
  captions?: CaptionConfig;
  zoom_punches?: ZoomPunch[];
  title?: string;
  description?: string;
  hashtags?: string[];
  platform_specific?: Record<
    string,
    {
      title: string;
      description?: string;
      hashtags: string[];
    }
  >;
}

export interface MomentScoreResult {
  keep: boolean;
  virality_score: number; // 0 - 100
  reason: string;
  category?: string;
  best_in?: number;
  best_out?: number;
  playbook_rules_applied?: string[];
  rule_violations?: string[];
}

export interface EditVersion {
  id: number;
  clip_id: number;
  version_number: number;
  edl_data: EditDecisionList;
  ai_reasoning?: string | null;
  model_used?: string | null;
  created_at: string;
}

export interface Clip {
  id: number;
  moment_id?: number | null;
  streamer_id: number;
  title: string;
  description?: string | null;
  hashtags?: string[] | null;
  duration?: number | null;
  status: ClipStatus;
  file_path?: string | null;
  thumbnail_path?: string | null;
  aspect_ratio: string;
  cost_tokens: number;
  cost_usd: number;
  created_at: string;
  updated_at: string;
  streamer?: Streamer;
  moment?: Moment;
  edit_versions?: EditVersion[];
  latest_edl?: EditDecisionList | null;
}

export interface PlaybookVersion {
  id: number;
  playbook_id: number;
  version_number: number;
  content: string;
  change_summary?: string | null;
  created_at: string;
}

export interface PlaybookFile {
  id: number;
  playbook_id: number;
  filename: string;
  file_type: string;
  extracted_text?: string | null;
  original_path?: string | null;
  created_at: string;
}

export interface PlaybookExample {
  id: number;
  playbook_id: number;
  example_type: 'good' | 'bad';
  url: string;
  notes?: string | null;
  transcript?: string | null;
  created_at: string;
}

export interface Playbook {
  id: number;
  name: string;
  description?: string | null;
  scope: PlaybookScope;
  target_id?: string | null;
  priority: number;
  enabled: boolean;
  content: string;
  created_at: string;
  updated_at: string;
  versions?: PlaybookVersion[];
  files?: PlaybookFile[];
  examples?: PlaybookExample[];
}

export interface PlaybookCreate {
  name: string;
  description?: string;
  scope: PlaybookScope;
  target_id?: string;
  priority?: number;
  enabled?: boolean;
  content: string;
}

export interface LayoutPreset {
  id: number;
  streamer_id?: number | null;
  name: string;
  layout_type: 'blurred_bg' | 'facecam_split' | 'face_track';
  facecam_box?: { x: number; y: number; w: number; h: number } | null;
  gameplay_box?: { x: number; y: number; w: number; h: number } | null;
  is_default: boolean;
  created_at: string;
}

export interface PromptTemplate {
  id: number;
  task_type: 'scoring' | 'edl' | 'title';
  template_text: string;
  system_prompt: string;
  default_model: string;
  created_at: string;
  updated_at: string;
}

export interface CostLedger {
  id: number;
  timestamp: string;
  job_type: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  audio_seconds: number;
  cost_usd: number;
}

export interface CostMetrics {
  daily_spend_usd: number;
  monthly_spend_usd: number;
  daily_cap_usd: number;
  remaining_today_usd: number;
  total_tokens_today: number;
  cost_by_provider: Record<string, number>;
  cost_by_task: Record<string, number>;
  recent_entries: CostLedger[];
}

// ---------------------------------------------------------------------------
// Jobs, Settings, Health & SSE
// ---------------------------------------------------------------------------

export interface Job {
  id: number;
  queue: JobQueue;
  job_type: string;
  status: JobStatus;
  params?: Record<string, any> | null;
  result?: Record<string, any> | null;
  error?: string | null;
  retries: number;
  max_retries: number;
  progress: number;
  log?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  streamer_id?: number | null;
  moment_id?: number | null;
}

export interface Setting {
  id: number;
  key: string;
  value: any;
  updated_at: string;
}

export interface ProviderKey {
  id: number;
  provider: string;
  key_name: string;
  masked_value: string;
  created_at: string;
  updated_at: string;
}

export interface HealthInfo {
  status: string;
  version: string;
  database: string;
  disk_usage?: {
    total_gb?: number;
    used_gb?: number;
    free_gb?: number;
    percent?: number;
    ring_buffers_gb?: number;
    clips_gb?: number;
  } | null;
  uptime_seconds?: number;
  active_recorders?: Array<{
    streamer_id: number;
    streamer_name: string;
    platform: string;
    status: string;
    duration: string;
  }>;
  queue_depths?: Record<string, number>;
  worker_alive?: boolean;
}

// SSE Event Payloads
export interface HypeUpdateEvent {
  streamer_id: number;
  score: number;
  signals?: Record<string, number>;
  messages_per_second: number;
  timestamp?: string;
}

export interface NewMomentEvent {
  moment: Moment;
}

export interface JobUpdateEvent {
  job: Job;
}

export interface StreamerStatusEvent {
  streamer_id: number;
  status: 'live' | 'ended' | 'offline' | 'error';
  viewer_count?: number;
}

export interface SystemAlertEvent {
  message: string;
  level: 'info' | 'warning' | 'error' | 'success';
}

export type SSEPayloadMap = {
  hype_update: HypeUpdateEvent;
  new_moment: NewMomentEvent;
  job_update: JobUpdateEvent;
  streamer_status: StreamerStatusEvent;
  system_alert: SystemAlertEvent;
};

// Vertical Thumbnails (GTA VI Style)
export interface ThumbnailResponse {
  thumbnail_url: string;
  file_path: string;
  mode: 'cinematic' | 'split';
  word1: string;
  word2: string;
  clip_id?: number | null;
  width: number;
  height: number;
  created_at: number;
}

export interface ThumbnailListItem {
  filename: string;
  thumbnail_url: string;
  clip_id?: number | null;
  mode: string;
  word1: string;
  word2: string;
  size_bytes: number;
  created_at: number;
}

export interface GenerateThumbnailRequest {
  clip_id?: number;
  word1?: string;
  word2?: string;
  mode?: 'cinematic' | 'split';
  face_x?: number;
  badge_title?: string;
  badge_sub?: string;
  hero_base64?: string;
}
