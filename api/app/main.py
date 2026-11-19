"""FastAPI application entry point with lifespan, CORS, and route registration."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.auth import ensure_default_user
from app.config import settings
from app.database import async_session, init_db
from app.models import Playbook, PlaybookVersion, PromptTemplate
from app.routes import (
    auth,
    clips,
    costs,
    health,
    jobs,
    live,
    moments,
    playbooks,
    presets,
    sessions,
    settings as settings_route,
    streamers,
    templates,
    thumbnails,
)


async def seed_defaults(session):
    """Seed default prompt templates and default playbook if not present."""
    # Default Prompt Templates
    tpl_count = await session.scalar(select(PromptTemplate.id).limit(1))
    if tpl_count is None:
        templates_to_seed = [
            PromptTemplate(
                task_type="scoring",
                default_model="gemini-1.5-flash",
                system_prompt="You are an expert short-form viral video editor and content strategist.",
                template_text=(
                    "Evaluate the following stream moment for virality, hook strength (1-10), "
                    "punchline clarity (1-10), and overall viral score (0-100).\n"
                    "Moment data: {moment_data}\nTranscript: {transcript}\nChat: {chat_summary}"
                ),
            ),
            PromptTemplate(
                task_type="edl",
                default_model="gemini-1.5-flash",
                system_prompt="You are an automated video editing director generating frame-accurate Edit Decision Lists (EDL).",
                template_text=(
                    "Create an EDL cutting all dead air over 0.7s, preserving the hook in the first 2 seconds, "
                    "and ending on the audience/chat reaction. Output valid JSON cuts and overlays.\n"
                    "Duration: {duration}s\nTranscript with timestamps: {timestamped_transcript}"
                ),
            ),
            PromptTemplate(
                task_type="title",
                default_model="gemini-1.5-flash",
                system_prompt="You are a social media copywriter writing high-CTR titles for TikTok, YouTube Shorts, and Reels.",
                template_text=(
                    "Generate 3 viral titles (casual, hyperbolic, emoji-heavy) and 5-8 relevant hashtags.\n"
                    "Streamer: @{streamer_handle}\nContext: {clip_summary}"
                ),
            ),
        ]
        session.add_all(templates_to_seed)

    # Default Global Playbook
    pb_count = await session.scalar(select(Playbook.id).limit(1))
    if pb_count is None:
        default_playbook_content = (
            "# Global Short-Form Clipping Playbook\n\n"
            "## What NOT to Clip (Hard Rules)\n"
            "- NO gambling segments or sponsor reads\n"
            "- NO clips with minors visible on camera\n"
            "- NO copyrighted music as the main audio (background game music is OK)\n"
            "- NO slurs, hate speech, or discriminatory content\n"
            "- NO personal information visible on screen (doxxing risk)\n"
            "- NO content the streamer has explicitly asked to keep off-clip\n"
            "- NO technical difficulties, loading screens, or AFK segments\n\n"
            "## Editing Style\n"
            "- Keep clips between 15-60 seconds\n"
            "- Hook must land in the first 2 seconds\n"
            "- Cut all dead air over 0.7 seconds\n"
            "- Prefer fast pacing over completeness\n"
            "- Include 2-3 seconds of context before the moment\n"
            "- Include the chat/audience reaction after the moment\n\n"
            "## Caption & Title Rules\n"
            "- Tone: casual, hyperbolic, emoji-heavy\n"
            "- Always credit streamer: 🎥 @{streamer_handle}\n"
            "- Use 5-8 hashtags per platform\n"
            "- No clickbait that misrepresents the clip content\n"
            "- Capitalize key words in titles for emphasis\n"
        )
        pb = Playbook(
            name="Global Short-Form Rules",
            description="Default system-wide guidelines for viral TikTok, Shorts, and Reels clipping",
            scope="global",
            priority=100,
            enabled=True,
            content=default_playbook_content,
        )
        session.add(pb)
        await session.flush()
        v1 = PlaybookVersion(
            playbook_id=pb.id,
            version_number=1,
            content=default_playbook_content,
            change_summary="System seed default",
        )
        session.add(v1)

    await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: initializes database, ensures admin user and defaults."""
    # Ensure media directory exists
    Path(settings.MEDIA_STORAGE_PATH).mkdir(parents=True, exist_ok=True)

    # Initialize tables
    await init_db()

    # Seed default admin user & defaults
    async with async_session() as session:
        await ensure_default_user(session)
        await seed_defaults(session)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(streamers.router)
app.include_router(moments.router)
app.include_router(sessions.router)
app.include_router(jobs.router)
app.include_router(settings_route.router)
app.include_router(live.router)
app.include_router(health.router)
# Phase 2 Routers
app.include_router(clips.router)
app.include_router(playbooks.router)
app.include_router(templates.router)
app.include_router(presets.router)
app.include_router(costs.router)
app.include_router(thumbnails.router)

# Mount media static directory for clips and 1080x1920 vertical thumbnails
media_dir = Path(settings.MEDIA_STORAGE_PATH)
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir), html=False), name="media")
