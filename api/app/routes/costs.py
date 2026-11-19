"""Cost tracking routes — track token usage, LLM/audio API spend, and budget caps."""

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import CostLedger, Setting, User
from app.schemas import (
    CostLedgerCreate,
    CostLedgerResponse,
    CostSummaryResponse,
)

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("", response_model=CostSummaryResponse)
async def get_cost_summary(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Calculate daily and monthly spend, token counts, budget cap status, and provider breakdown."""
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # All entries
    entries = (await db.execute(select(CostLedger))).scalars().all()

    daily_spend = 0.0
    monthly_spend = 0.0
    total_spend = 0.0

    daily_tokens = 0
    monthly_tokens = 0
    total_tokens = 0

    breakdown_by_provider: dict[str, float] = {}
    breakdown_by_job_type: dict[str, float] = {}

    for entry in entries:
        ts = entry.timestamp
        # SQLite datetime handling timezone
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        tokens = entry.input_tokens + entry.output_tokens
        usd = entry.cost_usd

        total_spend += usd
        total_tokens += tokens

        if ts >= start_of_month:
            monthly_spend += usd
            monthly_tokens += tokens

        if ts >= start_of_day:
            daily_spend += usd
            daily_tokens += tokens

        breakdown_by_provider[entry.provider] = breakdown_by_provider.get(entry.provider, 0.0) + usd
        breakdown_by_job_type[entry.job_type] = breakdown_by_job_type.get(entry.job_type, 0.0) + usd

    # Check spend cap setting
    cap_setting = await db.scalar(select(Setting).where(Setting.key == "daily_spend_cap_usd"))
    spend_cap_usd = 25.0
    if cap_setting and isinstance(cap_setting.value, (int, float)):
        spend_cap_usd = float(cap_setting.value)
    elif cap_setting and isinstance(cap_setting.value, dict) and "cap" in cap_setting.value:
        spend_cap_usd = float(cap_setting.value["cap"])

    cap_reached = daily_spend >= spend_cap_usd

    return CostSummaryResponse(
        daily_spend_usd=round(daily_spend, 4),
        monthly_spend_usd=round(monthly_spend, 4),
        total_spend_usd=round(total_spend, 4),
        daily_token_count=daily_tokens,
        monthly_token_count=monthly_tokens,
        total_token_count=total_tokens,
        spend_cap_usd=spend_cap_usd,
        cap_reached=cap_reached,
        breakdown_by_provider={k: round(v, 4) for k, v in breakdown_by_provider.items()},
        breakdown_by_job_type={k: round(v, 4) for k, v in breakdown_by_job_type.items()},
    )


@router.post("", response_model=CostLedgerResponse, status_code=status.HTTP_201_CREATED)
async def record_cost_entry(
    body: CostLedgerCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Record an inference or media processing cost event."""
    entry = CostLedger(
        job_type=body.job_type,
        provider=body.provider,
        model=body.model,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        audio_seconds=body.audio_seconds,
        cost_usd=body.cost_usd,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.get("/ledger", response_model=list[CostLedgerResponse])
async def list_cost_ledger(
    job_type: str | None = None,
    provider: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(CostLedger)
    if job_type:
        query = query.where(CostLedger.job_type == job_type)
    if provider:
        query = query.where(CostLedger.provider == provider)

    query = query.order_by(CostLedger.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())
