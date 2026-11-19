"""Prompt template routes — view and configure system prompts and templates for AI tasks."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import PromptTemplate, User
from app.schemas import (
    MessageResponse,
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[PromptTemplateResponse])
async def list_templates(
    task_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(PromptTemplate)
    if task_type:
        query = query.where(PromptTemplate.task_type == task_type)
    result = await db.execute(query.order_by(PromptTemplate.task_type))
    return list(result.scalars().all())


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    existing = await db.scalar(
        select(PromptTemplate).where(PromptTemplate.task_type == body.task_type)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template for task_type '{body.task_type}' already exists. Use PUT to update.",
        )

    tpl = PromptTemplate(
        task_type=body.task_type,
        template_text=body.template_text,
        system_prompt=body.system_prompt,
        default_model=body.default_model,
    )
    db.add(tpl)
    await db.flush()
    await db.refresh(tpl)
    return tpl


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    tpl = await db.scalar(select(PromptTemplate).where(PromptTemplate.id == template_id))
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
    return tpl


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_template(
    template_id: int,
    body: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    tpl = await db.scalar(select(PromptTemplate).where(PromptTemplate.id == template_id))
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(tpl, field, val)

    await db.flush()
    await db.refresh(tpl)
    return tpl


@router.delete("/{template_id}", response_model=MessageResponse)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    tpl = await db.scalar(select(PromptTemplate).where(PromptTemplate.id == template_id))
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
    await db.delete(tpl)
    await db.flush()
    return MessageResponse(message=f"Prompt template for '{tpl.task_type}' deleted")
