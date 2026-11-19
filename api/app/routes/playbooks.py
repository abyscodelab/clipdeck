"""Playbook routes — CRUD, version history, rollback, document upload, and rule test bench."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Playbook,
    PlaybookExample,
    PlaybookFile,
    PlaybookVersion,
    User,
)
from app.schemas import (
    MessageResponse,
    PlaybookCreate,
    PlaybookDetailResponse,
    PlaybookExampleCreate,
    PlaybookExampleResponse,
    PlaybookFileResponse,
    PlaybookResponse,
    PlaybookTestBenchRequest,
    PlaybookTestBenchResponse,
    PlaybookUpdate,
    PlaybookVersionResponse,
)

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(
    scope: str | None = None,
    enabled: bool | None = None,
    target_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Playbook)
    if scope:
        query = query.where(Playbook.scope == scope)
    if enabled is not None:
        query = query.where(Playbook.enabled == enabled)
    if target_id:
        query = query.where(Playbook.target_id == target_id)

    query = query.order_by(desc(Playbook.priority), Playbook.name)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=PlaybookDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    body: PlaybookCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    playbook = Playbook(
        name=body.name,
        description=body.description,
        scope=body.scope,
        target_id=body.target_id,
        priority=body.priority,
        enabled=body.enabled,
        content=body.content,
    )
    db.add(playbook)
    await db.flush()
    await db.refresh(playbook)

    # Automatically create version 1
    v1 = PlaybookVersion(
        playbook_id=playbook.id,
        version_number=1,
        content=playbook.content,
        change_summary="Initial version",
    )
    db.add(v1)
    await db.flush()

    stmt = (
        select(Playbook)
        .options(
            selectinload(Playbook.versions),
            selectinload(Playbook.files),
            selectinload(Playbook.examples),
        )
        .where(Playbook.id == playbook.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.get("/{playbook_id}", response_model=PlaybookDetailResponse)
async def get_playbook(
    playbook_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = (
        select(Playbook)
        .options(
            selectinload(Playbook.versions),
            selectinload(Playbook.files),
            selectinload(Playbook.examples),
        )
        .where(Playbook.id == playbook_id)
    )
    result = await db.execute(stmt)
    pb = result.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
    return pb


@router.put("/{playbook_id}", response_model=PlaybookDetailResponse)
async def update_playbook(
    playbook_id: int,
    body: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = (
        select(Playbook)
        .options(
            selectinload(Playbook.versions),
            selectinload(Playbook.files),
            selectinload(Playbook.examples),
        )
        .where(Playbook.id == playbook_id)
    )
    result = await db.execute(stmt)
    pb = result.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    content_changed = body.content is not None and body.content != pb.content

    update_dict = body.model_dump(exclude_unset=True, exclude={"change_summary"})
    for field, val in update_dict.items():
        setattr(pb, field, val)

    if content_changed:
        next_ver_num = len(pb.versions) + 1
        new_version = PlaybookVersion(
            playbook_id=pb.id,
            version_number=next_ver_num,
            content=pb.content,
            change_summary=body.change_summary or f"Version {next_ver_num} update",
        )
        db.add(new_version)

    await db.flush()
    result = await db.execute(stmt)
    return result.scalar_one()


@router.delete("/{playbook_id}", response_model=MessageResponse)
async def delete_playbook(
    playbook_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    pb = await db.scalar(select(Playbook).where(Playbook.id == playbook_id))
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
    await db.delete(pb)
    await db.flush()
    return MessageResponse(message=f"Playbook '{pb.name}' deleted")


@router.get("/{playbook_id}/versions", response_model=list[PlaybookVersionResponse])
async def list_playbook_versions(
    playbook_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = (
        select(PlaybookVersion)
        .where(PlaybookVersion.playbook_id == playbook_id)
        .order_by(desc(PlaybookVersion.version_number))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{playbook_id}/rollback/{version_id}", response_model=PlaybookDetailResponse)
async def rollback_playbook_version(
    playbook_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Roll back playbook content to a previous version and create a new version snapshot."""
    stmt = (
        select(Playbook)
        .options(
            selectinload(Playbook.versions),
            selectinload(Playbook.files),
            selectinload(Playbook.examples),
        )
        .where(Playbook.id == playbook_id)
    )
    result = await db.execute(stmt)
    pb = result.scalar_one_or_none()
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    target_ver = await db.scalar(
        select(PlaybookVersion).where(
            PlaybookVersion.id == version_id, PlaybookVersion.playbook_id == playbook_id
        )
    )
    if target_ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target version not found")

    pb.content = target_ver.content
    next_ver_num = len(pb.versions) + 1
    rollback_ver = PlaybookVersion(
        playbook_id=pb.id,
        version_number=next_ver_num,
        content=target_ver.content,
        change_summary=f"Rollback to version {target_ver.version_number}",
    )
    db.add(rollback_ver)
    await db.flush()

    result = await db.execute(stmt)
    return result.scalar_one()


@router.post("/{playbook_id}/upload", response_model=PlaybookFileResponse)
async def upload_playbook_file(
    playbook_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Upload guideline documents (.md, .txt, .json) to attach knowledge to a playbook."""
    pb = await db.scalar(select(Playbook).where(Playbook.id == playbook_id))
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    filename = file.filename or "uploaded_doc"
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ("md", "txt", "json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only .md, .txt, and .json documents are supported.",
        )

    content_bytes = await file.read()
    try:
        extracted_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        extracted_text = content_bytes.decode("latin-1")

    # If JSON, validate it parses nicely
    if ext == "json":
        try:
            parsed = json.loads(extracted_text)
            extracted_text = json.dumps(parsed, indent=2)
        except Exception:
            pass

    pf = PlaybookFile(
        playbook_id=pb.id,
        filename=filename,
        file_type=ext,
        extracted_text=extracted_text,
        original_path=f"uploads/{pb.id}/{filename}",
    )
    db.add(pf)
    await db.flush()
    await db.refresh(pf)
    return pf


@router.post("/{playbook_id}/examples", response_model=PlaybookExampleResponse, status_code=status.HTTP_201_CREATED)
async def add_playbook_example(
    playbook_id: int,
    body: PlaybookExampleCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    pb = await db.scalar(select(Playbook).where(Playbook.id == playbook_id))
    if pb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    example = PlaybookExample(
        playbook_id=pb.id,
        example_type=body.example_type,
        url=body.url,
        notes=body.notes,
        transcript=body.transcript,
    )
    db.add(example)
    await db.flush()
    await db.refresh(example)
    return example


@router.delete("/{playbook_id}/examples/{example_id}", response_model=MessageResponse)
async def delete_playbook_example(
    playbook_id: int,
    example_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    ex = await db.scalar(
        select(PlaybookExample).where(
            PlaybookExample.id == example_id, PlaybookExample.playbook_id == playbook_id
        )
    )
    if ex is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Example not found")
    await db.delete(ex)
    await db.flush()
    return MessageResponse(message="Example removed")


@router.post("/test-bench", response_model=PlaybookTestBenchResponse)
async def test_bench_run(
    body: PlaybookTestBenchRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Evaluate candidate text against all active playbooks and hard editorial rules."""
    query = select(Playbook).where(Playbook.enabled == True).order_by(desc(Playbook.priority))
    playbooks = (await db.execute(query)).scalars().all()

    rules_applied: list[str] = []
    rule_violations: list[str] = []
    recommendations: list[str] = []

    text_lower = body.sample_transcript.lower()

    # Hard guardrails check
    gambling_keywords = ["stake.com", "gambling", "crypto casino", "promo code roll", "slots", "roulette"]
    for kw in gambling_keywords:
        if kw in text_lower:
            rule_violations.append(f"Hard Rule Violation: Gambling segment detected ('{kw}')")

    minor_keywords = ["under 18", "minor", "child", "school age"]
    for kw in minor_keywords:
        if kw in text_lower:
            recommendations.append(f"Warning: Potential minor reference ('{kw}') - review footage carefully")

    doxxing_indicators = ["my ip address is", "social security", "credit card number", "home address"]
    for di in doxxing_indicators:
        if di in text_lower:
            rule_violations.append(f"Hard Rule Violation: Sensitive personal info indicator ('{di}')")

    # Positive editing rules checks
    for pb in playbooks:
        rules_applied.append(f"Applied playbook: {pb.name} (scope={pb.scope})")

    # Pace & structure recommendations
    word_count = len(body.sample_transcript.split())
    if word_count < 10:
        recommendations.append("Transcript is very short — verify there is a clear hook and reaction in audio/visuals.")
    elif word_count > 250:
        recommendations.append("Transcript is long (>250 words) — cut dead air to keep clip pacing under 60 seconds.")
    else:
        recommendations.append("Pacing and length align well with short-form 15-60s target.")

    passes_hard_rules = len(rule_violations) == 0

    return PlaybookTestBenchResponse(
        evaluated_playbooks=len(playbooks),
        rules_applied=rules_applied,
        rule_violations=rule_violations,
        passes_hard_rules=passes_hard_rules,
        recommendations=recommendations,
    )
