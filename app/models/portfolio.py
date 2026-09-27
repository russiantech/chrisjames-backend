# app/models/portfolio.py

"""The portfolio itself: projects, experience, skills, services, testimonials.

These are database-backed rather than hard-coded in the React app so Christopher
can edit the site from the dashboard without a deploy.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, PKMixin, TimestampMixin


class Project(Base, PKMixin, TimestampMixin):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    tagline: Mapped[str | None] = mapped_column(String(240))
    summary: Mapped[str | None] = mapped_column(Text)
    #: Long-form case study in markdown.
    body: Mapped[str | None] = mapped_column(Text)

    #: ``product`` | ``client`` | ``open_source`` | ``experiment``
    kind: Mapped[str] = mapped_column(String(20), default="product", index=True)
    role: Mapped[str | None] = mapped_column(String(160))
    client: Mapped[str | None] = mapped_column(String(160))
    stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    highlights: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: ``{"users": "12k", "uptime": "99.9%"}`` rendered as stat chips.
    metrics: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)

    cover_url: Mapped[str | None] = mapped_column(String(700))
    gallery: Mapped[list[str]] = mapped_column(JSON, default=list)
    icon: Mapped[str | None] = mapped_column(String(60))
    accent: Mapped[str] = mapped_column(String(24), default="primary")

    live_url: Mapped[str | None] = mapped_column(String(500))
    repo_url: Mapped[str | None] = mapped_column(String(500))
    case_study_url: Mapped[str | None] = mapped_column(String(500))

    started_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    #: ``live`` | ``beta`` | ``archived`` | ``in_progress``
    state: Mapped[str] = mapped_column(String(20), default="live")

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)


class Experience(Base, PKMixin, TimestampMixin):
    """A role on the CV timeline."""

    __tablename__ = "experiences"

    organisation: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(120))
    #: ``full_time`` | ``contract`` | ``freelance`` | ``founder`` | ``education``
    employment_type: Mapped[str] = mapped_column(String(24), default="full_time")
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[list[str]] = mapped_column(JSON, default=list)
    stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    logo_url: Mapped[str | None] = mapped_column(String(700))
    website: Mapped[str | None] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class SkillGroup(Base, PKMixin, TimestampMixin):
    __tablename__ = "skill_groups"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(180), index=True, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(60))
    accent: Mapped[str] = mapped_column(String(24), default="primary")
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    

    skills: Mapped[list["Skill"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Skill.position",
        lazy="selectin",
    )


class Skill(Base, PKMixin, TimestampMixin):
    __tablename__ = "skills"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("skill_groups.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    #: 1–5, rendered as a small proficiency bar.
    level: Mapped[int] = mapped_column(Integer, default=4)
    years: Mapped[float | None] = mapped_column(Integer)
    icon: Mapped[str | None] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(Integer, default=0)

    group: Mapped[SkillGroup] = relationship(back_populates="skills")


class Service(Base, PKMixin, TimestampMixin):
    """What Christopher offers — the cards under "What clients ask for"."""

    __tablename__ = "services"

    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(60), default="bi-code-slash")
    accent: Mapped[str] = mapped_column(String(24), default="primary")
    bullets: Mapped[list[str]] = mapped_column(JSON, default=list)
    starting_price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Testimonial(Base, PKMixin, TimestampMixin):
    __tablename__ = "testimonials"

    author_name: Mapped[str] = mapped_column(String(120))
    author_title: Mapped[str | None] = mapped_column(String(160))
    author_company: Mapped[str | None] = mapped_column(String(160))
    avatar_url: Mapped[str | None] = mapped_column(String(700))
    quote: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    source_url: Mapped[str | None] = mapped_column(String(500))
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class SiteSetting(Base, PKMixin, TimestampMixin):
    """Runtime-editable key/value configuration.

    Anything here overrides the matching field in ``app.core.config`` — that is
    how "auto-publish visitor submissions" can be flipped from the dashboard.
    """

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value: Mapped[Any] = mapped_column(JSON)
    #: ``string`` | ``bool`` | ``int`` | ``json`` — drives the settings form widget.
    value_type: Mapped[str] = mapped_column(String(16), default="string")
    group: Mapped[str] = mapped_column(String(40), default="general", index=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str | None] = mapped_column(Text)
    #: Public settings are exposed to unauthenticated clients via /settings/public.
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base, PKMixin, TimestampMixin):
    """Who did what, to which record, and from where."""

    __tablename__ = "audit_logs"

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_label: Mapped[str | None] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(60), index=True)
    subject_type: Mapped[str | None] = mapped_column(String(40), index=True)
    subject_id: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(String(300))
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
