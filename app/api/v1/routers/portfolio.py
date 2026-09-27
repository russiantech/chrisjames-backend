# # app/api/v1/routers/portfolio.py
# """Portfolio content: projects, experience, skills, services, testimonials."""

# from __future__ import annotations

# from typing import Annotated, Any

# from fastapi import APIRouter, status
# from sqlalchemy import select

# from app.api.deps import DbSession, require
# from app.core.exceptions import NotFound
# from app.core.permissions import Perm
# from app.models.portfolio import (
#     Experience,
#     Project,
#     Service,
#     Skill,
#     SkillGroup,
#     Testimonial,
# )
# from app.models.user import User
# from app.schemas.common import Message
# from app.schemas.portfolio import (
#     ExperienceRead,
#     ExperienceWrite,
#     ProjectRead,
#     ProjectSummary,
#     ProjectWrite,
#     ServiceRead,
#     ServiceWrite,
#     SkillGroupRead,
#     SkillGroupWrite,
#     TestimonialRead,
#     TestimonialWrite,
# )
# from app.services.text import slugify

# router = APIRouter(tags=["portfolio"])

# Manager = Annotated[User, require(Perm.PORTFOLIO_MANAGE)]


# # ------------------------------------------------------------------ projects
# @router.get("/projects", response_model=list[ProjectSummary])
# async def list_projects(
#     db: DbSession, kind: str | None = None, featured: bool | None = None
# ) -> list[Project]:
#     stmt = select(Project).where(Project.is_published.is_(True))
#     if kind:
#         stmt = stmt.where(Project.kind == kind)
#     if featured is not None:
#         stmt = stmt.where(Project.is_featured.is_(featured))
#     rows = await db.scalars(stmt.order_by(Project.position, Project.id.desc()))
#     return list(rows.all())


# @router.get("/projects/{slug}", response_model=ProjectRead)
# async def read_project(slug: str, db: DbSession) -> Project:
#     project = await db.scalar(select(Project).where(Project.slug == slug))
#     if project is None or not project.is_published:
#         raise NotFound("No project with that address.")
#     project.view_count += 1
#     await db.commit()
#     return project


# @router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
# async def create_project(payload: ProjectWrite, db: DbSession, _: Manager) -> Project:
#     project = Project(
#         **payload.model_dump(exclude={"slug"}),
#         slug=payload.slug or slugify(payload.title),
#     )
#     db.add(project)
#     await db.commit()
#     return project


# @router.patch("/projects/{project_id}", response_model=ProjectRead)
# async def update_project(
#     project_id: int, payload: ProjectWrite, db: DbSession, _: Manager
# ) -> Project:
#     project = await db.get(Project, project_id)
#     if project is None:
#         raise NotFound("No project with that id.")
#     for field, value in payload.model_dump(exclude_unset=True).items():
#         setattr(project, field, value)
#     await db.commit()
#     return project


# @router.delete("/projects/{project_id}", response_model=Message)
# async def delete_project(project_id: int, db: DbSession, _: Manager) -> Message:
#     project = await db.get(Project, project_id)
#     if project is None:
#         raise NotFound("No project with that id.")
#     await db.delete(project)
#     await db.commit()
#     return Message(detail="Project removed.")


# # ---------------------------------------------------------------- experience
# @router.get("/experience", response_model=list[ExperienceRead])
# async def list_experience(db: DbSession) -> list[Experience]:
#     rows = await db.scalars(
#         select(Experience)
#         .where(Experience.is_published.is_(True))
#         .order_by(Experience.is_current.desc(), Experience.started_on.desc())
#     )
#     return list(rows.all())


# @router.post("/experience", response_model=ExperienceRead, status_code=201)
# async def create_experience(
#     payload: ExperienceWrite, db: DbSession, _: Manager
# ) -> Experience:
#     row = Experience(**payload.model_dump())
#     db.add(row)
#     await db.commit()
#     return row


# @router.patch("/experience/{experience_id}", response_model=ExperienceRead)
# async def update_experience(
#     experience_id: int, payload: ExperienceWrite, db: DbSession, _: Manager
# ) -> Experience:
#     row = await db.get(Experience, experience_id)
#     if row is None:
#         raise NotFound("No role with that id.")
#     for field, value in payload.model_dump(exclude_unset=True).items():
#         setattr(row, field, value)
#     await db.commit()
#     return row


# @router.delete("/experience/{experience_id}", response_model=Message)
# async def delete_experience(experience_id: int, db: DbSession, _: Manager) -> Message:
#     row = await db.get(Experience, experience_id)
#     if row is None:
#         raise NotFound("No role with that id.")
#     await db.delete(row)
#     await db.commit()
#     return Message(detail="Role removed.")


# # -------------------------------------------------------------------- skills
# @router.get("/skills", response_model=list[SkillGroupRead])
# async def list_skills(db: DbSession) -> list[SkillGroup]:
#     rows = await db.scalars(select(SkillGroup).order_by(SkillGroup.position))
#     return list(rows.all())


# @router.put("/skills", response_model=list[SkillGroupRead])
# async def replace_skills(
#     payload: list[SkillGroupWrite], db: DbSession, _: Manager
# ) -> list[SkillGroup]:
#     """Replace the whole skills matrix in one call — it is edited as a unit."""
#     for existing in (await db.scalars(select(SkillGroup))).all():
#         await db.delete(existing)
#     await db.flush()

#     created: list[SkillGroup] = []
#     for position, group_payload in enumerate(payload):
#         group = SkillGroup(
#             **group_payload.model_dump(exclude={"skills"}), position=position
#         )
#         db.add(group)
#         await db.flush()
#         for skill_position, skill in enumerate(group_payload.skills):
#             group.skills.append(Skill(**skill.model_dump(), position=skill_position))
#         created.append(group)

#     await db.commit()
#     return created


# # ------------------------------------------------------------------ services
# @router.get("/services", response_model=list[ServiceRead])
# async def list_services(db: DbSession) -> list[Service]:
#     rows = await db.scalars(
#         select(Service).where(Service.is_published.is_(True)).order_by(Service.position)
#     )
#     return list(rows.all())


# @router.post("/services", response_model=ServiceRead, status_code=201)
# async def create_service(payload: ServiceWrite, db: DbSession, _: Manager) -> Service:
#     row = Service(
#         **payload.model_dump(exclude={"slug"}), slug=payload.slug or slugify(payload.title)
#     )
#     db.add(row)
#     await db.commit()
#     return row


# @router.patch("/services/{service_id}", response_model=ServiceRead)
# async def update_service(
#     service_id: int, payload: ServiceWrite, db: DbSession, _: Manager
# ) -> Service:
#     row = await db.get(Service, service_id)
#     if row is None:
#         raise NotFound("No service with that id.")
#     for field, value in payload.model_dump(exclude_unset=True, exclude={"slug"}).items():
#         setattr(row, field, value)
#     await db.commit()
#     return row


# # -------------------------------------------------------------- testimonials
# @router.get("/testimonials", response_model=list[TestimonialRead])
# async def list_testimonials(
#     db: DbSession, featured: bool | None = None
# ) -> list[Testimonial]:
#     stmt = select(Testimonial).where(Testimonial.is_published.is_(True))
#     if featured is not None:
#         stmt = stmt.where(Testimonial.is_featured.is_(featured))
#     rows = await db.scalars(stmt.order_by(Testimonial.position, Testimonial.id))
#     return list(rows.all())


# @router.post("/testimonials", response_model=TestimonialRead, status_code=201)
# async def create_testimonial(
#     payload: TestimonialWrite, db: DbSession, _: Manager
# ) -> Testimonial:
#     row = Testimonial(**payload.model_dump())
#     db.add(row)
#     await db.commit()
#     return row


# @router.delete("/testimonials/{testimonial_id}", response_model=Message)
# async def delete_testimonial(
#     testimonial_id: int, db: DbSession, _: Manager
# ) -> Message:
#     row = await db.get(Testimonial, testimonial_id)
#     if row is None:
#         raise NotFound("No testimonial with that id.")
#     await db.delete(row)
#     await db.commit()
#     return Message(detail="Testimonial removed.")





# v2
"""Portfolio content: projects, experience, skills, services, testimonials."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DbSession, require
from app.core.exceptions import NotFound
from app.core.permissions import Perm
from app.models.portfolio import (
    Experience,
    Project,
    Service,
    Skill,
    SkillGroup,
    Testimonial,
)
from app.models.user import User
from app.schemas.common import Message
from app.schemas.portfolio import (
    ExperienceRead,
    ExperienceWrite,
    ProjectRead,
    ProjectSummary,
    ProjectWrite,
    ReorderPayload,
    ServiceRead,
    ServiceWrite,
    SkillGroupRead,
    SkillGroupWrite,
    TestimonialRead,
    TestimonialWrite,
)
from app.services.text import slugify

router = APIRouter(tags=["portfolio"])

Manager = Annotated[User, require(Perm.PORTFOLIO_MANAGE)]


async def _apply_reorder(db: DbSession, model: type, ids: list[int]) -> None:
    """Set `.position` to each id's index in the given order. Unknown ids are
    skipped rather than raising — the dashboard sending a stale list is a
    normal race, not an error worth failing the whole request over."""
    for position, item_id in enumerate(ids):
        row = await db.get(model, item_id)
        if row is not None:
            row.position = position
    await db.commit()


# ------------------------------------------------------------------ projects
# NOTE: /projects/admin must stay registered before /projects/{slug} — both
# are GET on a single path segment, so if the dynamic slug route came first
# it would swallow "admin" as if it were a (nonexistent) project's slug.
@router.get("/projects/admin", response_model=list[ProjectRead])
async def list_projects_admin(db: DbSession, _: Manager) -> list[Project]:
    """Every project, published or not, for the dashboard's own list view."""
    rows = await db.scalars(select(Project).order_by(Project.position, Project.id.desc()))
    return list(rows.all())


@router.get("/projects/id/{project_id}", response_model=ProjectRead)
async def read_project_by_id(project_id: int, db: DbSession, _: Manager) -> Project:
    """Fetch by id regardless of publish state — what the edit form loads
    from. (Two path segments here, so no ordering conflict with the
    single-segment /projects/{slug} route below.)"""
    project = await db.get(Project, project_id)
    if project is None:
        raise NotFound("No project with that id.")
    return project


@router.post("/projects/reorder", response_model=Message)
async def reorder_projects(payload: ReorderPayload, db: DbSession, _: Manager) -> Message:
    await _apply_reorder(db, Project, payload.ids)
    return Message(detail="Order updated.")


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects(
    db: DbSession, kind: str | None = None, featured: bool | None = None
) -> list[Project]:
    stmt = select(Project).where(Project.is_published.is_(True))
    if kind:
        stmt = stmt.where(Project.kind == kind)
    if featured is not None:
        stmt = stmt.where(Project.is_featured.is_(featured))
    rows = await db.scalars(stmt.order_by(Project.position, Project.id.desc()))
    return list(rows.all())


@router.get("/projects/{slug}", response_model=ProjectRead)
async def read_project(slug: str, db: DbSession) -> Project:
    project = await db.scalar(select(Project).where(Project.slug == slug))
    if project is None or not project.is_published:
        raise NotFound("No project with that address.")
    project.view_count += 1
    await db.commit()
    return project


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectWrite, db: DbSession, _: Manager) -> Project:
    project = Project(
        **payload.model_dump(exclude={"slug"}),
        slug=payload.slug or slugify(payload.title),
    )
    db.add(project)
    await db.commit()
    return project


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int, payload: ProjectWrite, db: DbSession, _: Manager
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise NotFound("No project with that id.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    return project


@router.delete("/projects/{project_id}", response_model=Message)
async def delete_project(project_id: int, db: DbSession, _: Manager) -> Message:
    project = await db.get(Project, project_id)
    if project is None:
        raise NotFound("No project with that id.")
    await db.delete(project)
    await db.commit()
    return Message(detail="Project removed.")


# ---------------------------------------------------------------- experience
@router.get("/experience/admin", response_model=list[ExperienceRead])
async def list_experience_admin(db: DbSession, _: Manager) -> list[Experience]:
    rows = await db.scalars(
        select(Experience).order_by(Experience.position, Experience.started_on.desc())
    )
    return list(rows.all())


@router.post("/experience/reorder", response_model=Message)
async def reorder_experience(payload: ReorderPayload, db: DbSession, _: Manager) -> Message:
    await _apply_reorder(db, Experience, payload.ids)
    return Message(detail="Order updated.")


@router.get("/experience", response_model=list[ExperienceRead])
async def list_experience(db: DbSession) -> list[Experience]:
    rows = await db.scalars(
        select(Experience)
        .where(Experience.is_published.is_(True))
        .order_by(Experience.is_current.desc(), Experience.started_on.desc())
    )
    return list(rows.all())


@router.post("/experience", response_model=ExperienceRead, status_code=201)
async def create_experience(
    payload: ExperienceWrite, db: DbSession, _: Manager
) -> Experience:
    row = Experience(**payload.model_dump())
    db.add(row)
    await db.commit()
    return row


@router.patch("/experience/{experience_id}", response_model=ExperienceRead)
async def update_experience(
    experience_id: int, payload: ExperienceWrite, db: DbSession, _: Manager
) -> Experience:
    row = await db.get(Experience, experience_id)
    if row is None:
        raise NotFound("No role with that id.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.delete("/experience/{experience_id}", response_model=Message)
async def delete_experience(experience_id: int, db: DbSession, _: Manager) -> Message:
    row = await db.get(Experience, experience_id)
    if row is None:
        raise NotFound("No role with that id.")
    await db.delete(row)
    await db.commit()
    return Message(detail="Role removed.")


# -------------------------------------------------------------------- skills
@router.get("/skills", response_model=list[SkillGroupRead])
async def list_skills(db: DbSession) -> list[SkillGroup]:
    rows = await db.scalars(select(SkillGroup).order_by(SkillGroup.position))
    return list(rows.all())


@router.put("/skills", response_model=list[SkillGroupRead])
async def replace_skills(
    payload: list[SkillGroupWrite], db: DbSession, _: Manager
) -> list[SkillGroup]:
    """Replace the whole skills matrix in one call — it is edited as a unit.
    List order IS the display order, so this already covers create, update,
    delete, and reorder for skills; no separate /skills/reorder needed."""
    for existing in (await db.scalars(select(SkillGroup))).all():
        await db.delete(existing)
    await db.flush()

    created: list[SkillGroup] = []
    for position, group_payload in enumerate(payload):
        group = SkillGroup(
            **group_payload.model_dump(exclude={"skills"}), position=position
        )
        db.add(group)
        await db.flush()
        for skill_position, skill in enumerate(group_payload.skills):
            group.skills.append(Skill(**skill.model_dump(), position=skill_position))
        created.append(group)

    await db.commit()
    return created


# ------------------------------------------------------------------ services
@router.get("/services/admin", response_model=list[ServiceRead])
async def list_services_admin(db: DbSession, _: Manager) -> list[Service]:
    rows = await db.scalars(select(Service).order_by(Service.position))
    return list(rows.all())


@router.post("/services/reorder", response_model=Message)
async def reorder_services(payload: ReorderPayload, db: DbSession, _: Manager) -> Message:
    await _apply_reorder(db, Service, payload.ids)
    return Message(detail="Order updated.")


@router.get("/services", response_model=list[ServiceRead])
async def list_services(db: DbSession) -> list[Service]:
    rows = await db.scalars(
        select(Service).where(Service.is_published.is_(True)).order_by(Service.position)
    )
    return list(rows.all())


@router.post("/services", response_model=ServiceRead, status_code=201)
async def create_service(payload: ServiceWrite, db: DbSession, _: Manager) -> Service:
    row = Service(
        **payload.model_dump(exclude={"slug"}), slug=payload.slug or slugify(payload.title)
    )
    db.add(row)
    await db.commit()
    return row


@router.patch("/services/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: int, payload: ServiceWrite, db: DbSession, _: Manager
) -> Service:
    row = await db.get(Service, service_id)
    if row is None:
        raise NotFound("No service with that id.")
    for field, value in payload.model_dump(exclude_unset=True, exclude={"slug"}).items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.delete("/services/{service_id}", response_model=Message)
async def delete_service(service_id: int, db: DbSession, _: Manager) -> Message:
    """This didn't exist before — a service could be created and edited but
    never removed."""
    row = await db.get(Service, service_id)
    if row is None:
        raise NotFound("No service with that id.")
    await db.delete(row)
    await db.commit()
    return Message(detail="Service removed.")


# -------------------------------------------------------------- testimonials
@router.get("/testimonials/admin", response_model=list[TestimonialRead])
async def list_testimonials_admin(db: DbSession, _: Manager) -> list[Testimonial]:
    rows = await db.scalars(select(Testimonial).order_by(Testimonial.position, Testimonial.id))
    return list(rows.all())


@router.post("/testimonials/reorder", response_model=Message)
async def reorder_testimonials(payload: ReorderPayload, db: DbSession, _: Manager) -> Message:
    await _apply_reorder(db, Testimonial, payload.ids)
    return Message(detail="Order updated.")


@router.get("/testimonials", response_model=list[TestimonialRead])
async def list_testimonials(
    db: DbSession, featured: bool | None = None
) -> list[Testimonial]:
    stmt = select(Testimonial).where(Testimonial.is_published.is_(True))
    if featured is not None:
        stmt = stmt.where(Testimonial.is_featured.is_(featured))
    rows = await db.scalars(stmt.order_by(Testimonial.position, Testimonial.id))
    return list(rows.all())


@router.post("/testimonials", response_model=TestimonialRead, status_code=201)
async def create_testimonial(
    payload: TestimonialWrite, db: DbSession, _: Manager
) -> Testimonial:
    row = Testimonial(**payload.model_dump())
    db.add(row)
    await db.commit()
    return row


@router.patch("/testimonials/{testimonial_id}", response_model=TestimonialRead)
async def update_testimonial(
    testimonial_id: int, payload: TestimonialWrite, db: DbSession, _: Manager
) -> Testimonial:
    """This didn't exist before either — a typo in a quote could never be
    fixed without deleting and recreating the whole testimonial."""
    row = await db.get(Testimonial, testimonial_id)
    if row is None:
        raise NotFound("No testimonial with that id.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return row


@router.delete("/testimonials/{testimonial_id}", response_model=Message)
async def delete_testimonial(
    testimonial_id: int, db: DbSession, _: Manager
) -> Message:
    row = await db.get(Testimonial, testimonial_id)
    if row is None:
        raise NotFound("No testimonial with that id.")
    await db.delete(row)
    await db.commit()
    return Message(detail="Testimonial removed.")
