"""Categories, tags and series."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import DbSession, require
from app.core.exceptions import Conflict, NotFound
from app.core.permissions import Perm
from app.models.enums import PostStatus
from app.models.post import Post
from app.models.taxonomy import Category, Series, Tag
from app.models.user import User
from app.schemas.common import Message
from app.schemas.post import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    SeriesRead,
    TagCreate,
    TagRead,
)
from app.services.text import slugify

router = APIRouter(tags=["taxonomy"])

Curator = Annotated[User, require(Perm.TAXONOMY_MANAGE)]


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(db: DbSession, with_counts: bool = True) -> list[CategoryRead]:
    rows = (
        await db.scalars(
            select(Category).where(Category.is_visible.is_(True)).order_by(Category.position)
        )
    ).all()
    out = [CategoryRead.model_validate(row) for row in rows]

    if with_counts and out:
        counts = await db.execute(
            select(Post.category_id, func.count(Post.id))
            .where(Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
            .group_by(Post.category_id)
        )
        lookup = dict(counts.all())
        for item in out:
            item.post_count = lookup.get(item.id, 0)
    return out


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, db: DbSession, _: Curator) -> Category:
    slug = payload.slug or slugify(payload.name)
    if await db.scalar(select(Category).where(Category.slug == slug)):
        raise Conflict("A category with that address already exists.")
    row = Category(**payload.model_dump(exclude={"slug"}), slug=slug)
    db.add(row)
    await db.commit()
    return row


@router.patch("/categories/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: int, payload: CategoryUpdate, db: DbSession, _: Curator
) -> Category:
    row = await db.get(Category, category_id)
    if row is None:
        raise NotFound("No category with that id.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.delete("/categories/{category_id}", response_model=Message)
async def delete_category(category_id: int, db: DbSession, _: Curator) -> Message:
    row = await db.get(Category, category_id)
    if row is None:
        raise NotFound("No category with that id.")
    await db.delete(row)  # posts fall back to no category
    await db.commit()
    return Message(detail="Category removed. Its posts are now uncategorised.")


@router.get("/tags", response_model=list[TagRead])
async def list_tags(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=60)] = None,
    limit: int = 50,
) -> list[Tag]:
    stmt = select(Tag)
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{q}%"))
    rows = await db.scalars(
        stmt.order_by(Tag.usage_count.desc(), Tag.name).limit(min(limit, 200))
    )
    return list(rows.all())


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(payload: TagCreate, db: DbSession, _: Curator) -> Tag:
    slug = slugify(payload.name)
    existing = await db.scalar(select(Tag).where(Tag.slug == slug))
    if existing is not None:
        return existing
    row = Tag(name=payload.name, slug=slug, accent=payload.accent, description=payload.description)
    db.add(row)
    await db.commit()
    return row


@router.get("/series", response_model=list[SeriesRead])
async def list_series(db: DbSession) -> list[Series]:
    rows = await db.scalars(select(Series).order_by(Series.created_at.desc()))
    return list(rows.all())
