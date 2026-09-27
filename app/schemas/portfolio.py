# app/schemas/portfolio.py
"""Portfolio content schemas."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field

from app.schemas.common import ORMSchema, Schema


class ProjectSummary(ORMSchema):
    id: int
    title: str
    slug: str
    tagline: str | None = None
    summary: str | None = None
    kind: str
    role: str | None = None
    client: str | None = None
    stack: list[str] = Field(default_factory=list)
    metrics: dict[str, str] = Field(default_factory=dict)
    cover_url: str | None = None
    icon: str | None = None
    accent: str
    live_url: str | None = None
    repo_url: str | None = None
    state: str
    is_featured: bool
    position: int


class ProjectRead(ProjectSummary):
    body: str | None = None
    highlights: list[str] = Field(default_factory=list)
    gallery: list[str] = Field(default_factory=list)
    case_study_url: str | None = None
    started_on: date | None = None
    ended_on: date | None = None
    view_count: int


class ProjectWrite(Schema):
    title: Annotated[str, Field(min_length=2, max_length=160)]
    slug: str | None = None
    tagline: Annotated[str | None, Field(max_length=240)] = None
    summary: str | None = None
    body: str | None = None
    kind: str = "product"
    role: str | None = None
    client: str | None = None
    stack: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    metrics: dict[str, str] = Field(default_factory=dict)
    cover_url: str | None = None
    gallery: list[str] = Field(default_factory=list)
    icon: str | None = None
    accent: str = "primary"
    live_url: str | None = None
    repo_url: str | None = None
    case_study_url: str | None = None
    started_on: date | None = None
    ended_on: date | None = None
    state: str = "live"
    is_featured: bool = False
    is_published: bool = True
    position: int = 0


class ExperienceRead(ORMSchema):
    id: int
    organisation: str
    title: str
    location: str | None = None
    employment_type: str
    started_on: date
    ended_on: date | None = None
    is_current: bool
    summary: str | None = None
    achievements: list[str] = Field(default_factory=list)
    stack: list[str] = Field(default_factory=list)
    logo_url: str | None = None
    website: str | None = None


class ExperienceWrite(Schema):
    organisation: Annotated[str, Field(max_length=160)]
    title: Annotated[str, Field(max_length=160)]
    location: str | None = None
    employment_type: str = "full_time"
    started_on: date
    ended_on: date | None = None
    is_current: bool = False
    summary: str | None = None
    achievements: list[str] = Field(default_factory=list)
    stack: list[str] = Field(default_factory=list)
    logo_url: str | None = None
    website: str | None = None
    position: int = 0
    is_published: bool = True


class SkillRead(ORMSchema):
    id: int
    name: str
    level: int
    icon: str | None = None


class SkillWrite(Schema):
    name: Annotated[str, Field(max_length=80)]
    level: Annotated[int, Field(ge=1, le=5)] = 4
    icon: str | None = None


class SkillGroupRead(ORMSchema):
    id: int
    name: str
    icon: str | None = None
    accent: str
    description: str | None = None
    skills: list[SkillRead] = Field(default_factory=list)


class SkillGroupWrite(Schema):
    name: Annotated[str, Field(max_length=120)]
    icon: str | None = None
    accent: str = "primary"
    description: str | None = None
    skills: list[SkillWrite] = Field(default_factory=list)


class ServiceRead(ORMSchema):
    id: int
    title: str
    slug: str
    summary: str
    body: str | None = None
    icon: str
    accent: str
    bullets: list[str] = Field(default_factory=list)
    starting_price_minor: int | None = None
    currency: str
    position: int


class ServiceWrite(Schema):
    title: Annotated[str, Field(max_length=160)]
    slug: str | None = None
    summary: str
    body: str | None = None
    icon: str = "bi-code-slash"
    accent: str = "primary"
    bullets: list[str] = Field(default_factory=list)
    starting_price_minor: int | None = None
    currency: str = "USD"
    position: int = 0
    is_published: bool = True


class TestimonialRead(ORMSchema):
    id: int
    author_name: str
    author_title: str | None = None
    author_company: str | None = None
    avatar_url: str | None = None
    quote: str
    rating: int
    source_url: str | None = None
    is_featured: bool


class TestimonialWrite(Schema):
    author_name: Annotated[str, Field(max_length=120)]
    author_title: str | None = None
    author_company: str | None = None
    avatar_url: str | None = None
    quote: str
    rating: Annotated[int, Field(ge=1, le=5)] = 5
    source_url: str | None = None
    project_id: int | None = None
    is_featured: bool = False
    is_published: bool = True
    position: int = 0


class ReorderPayload(Schema):
    """Body for the /reorder endpoints — ids in the new display order."""

    ids: list[int] = Field(..., min_length=1, description="IDs in the new display order")
    