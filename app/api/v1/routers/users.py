"""People and roles."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, Pagination, require
from app.core.exceptions import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    Perm,
)
from app.core.security import hash_password
from app.models.enums import UserStatus
from app.models.user import Role, User
from app.schemas.common import Message, Page
from app.schemas.user import (
    PermissionInfo,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserAdminCreate,
    UserAdminUpdate,
    UserMe,
    UserPublic,
    UserRead,
    UserUpdate,
)

router = APIRouter(tags=["people"])


@router.patch("/users/me", response_model=UserMe)
async def update_me(payload: UserUpdate, db: DbSession, user: CurrentUser) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return user


@router.get("/users/{username}", response_model=UserPublic)
async def read_public_profile(username: str, db: DbSession) -> User:
    row = await db.scalar(
        select(User).where(User.username == username.lower(), User.deleted_at.is_(None))
    )
    if row is None or row.status != UserStatus.ACTIVE:
        raise NotFound("No such profile.")
    return row


@router.get("/admin/users", response_model=Page[UserRead])
async def list_users(
    db: DbSession,
    page: Pagination,
    _: Annotated[User, require(Perm.USER_READ)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    role: str | None = None,
    user_status: Annotated[str | None, Query(alias="status")] = None,
) -> Page[UserRead]:
    stmt = select(User).where(User.deleted_at.is_(None)).options(selectinload(User.roles))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(User.email.ilike(like), User.username.ilike(like), User.full_name.ilike(like))
        )
    if role:
        stmt = stmt.join(User.roles).where(Role.name == role)
    if user_status:
        stmt = stmt.where(User.status == user_status)

    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        await db.scalars(
            stmt.order_by(User.created_at.desc()).offset(page.offset).limit(page.limit)
        )
    ).unique().all()
    return Page.build(
        [UserRead.model_validate(row) for row in rows], total or 0, page.page, page.per_page
    )


@router.post("/admin/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserAdminCreate,
    db: DbSession,
    actor: Annotated[User, require(Perm.USER_MANAGE)],
) -> User:
    clash = await db.scalar(
        select(User).where(
            or_(User.email == payload.email.lower(), User.username == payload.username)
        )
    )
    if clash is not None:
        raise Conflict("That e-mail address or username is already in use.")

    roles = (
        await db.scalars(select(Role).where(Role.name.in_(payload.role_names)))
    ).all()
    if len(roles) != len(payload.role_names):
        raise ValidationFailed("One of those role names does not exist.")
    if any(role.is_superuser for role in roles) and not actor.is_superuser:
        raise PermissionDenied("Only the owner can grant a superuser role.")

    user = User(
        email=payload.email.lower(),
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        status=payload.status,
    )
    user.roles.extend(roles)
    db.add(user)
    await db.flush()

    if payload.send_invite_email:
        from app.core.config import settings
        from app.services.email import send_email

        await send_email(
            db,
            to_address=user.email,
            template="welcome",
            context={"name": user.display_name, "action_url": f"{settings.SITE_URL}/login"},
        )

    await db.commit()
    await db.refresh(user, ["roles"])
    return user


@router.patch("/admin/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: DbSession,
    actor: Annotated[User, require(Perm.USER_MANAGE)],
) -> User:
    user = await db.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    if user is None:
        raise NotFound("No account with that id.")
    if user.is_superuser and not actor.is_superuser:
        raise PermissionDenied("Only the owner can change an owner account.")

    data = payload.model_dump(exclude_unset=True, exclude={"role_names"})
    for field, value in data.items():
        setattr(user, field, value)

    if payload.role_names is not None:
        roles = (
            await db.scalars(select(Role).where(Role.name.in_(payload.role_names)))
        ).all()
        if any(role.is_superuser for role in roles) and not actor.is_superuser:
            raise PermissionDenied("Only the owner can grant a superuser role.")
        user.roles = list(roles)

    await db.commit()
    await db.refresh(user, ["roles"])
    return user


@router.delete("/admin/users/{user_id}", response_model=Message)
async def deactivate_user(
    user_id: int,
    db: DbSession,
    actor: Annotated[User, require(Perm.USER_MANAGE)],
) -> Message:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFound("No account with that id.")
    if user.id == actor.id:
        raise ValidationFailed("You cannot deactivate your own account here.")
    if user.is_superuser and not actor.is_superuser:
        raise PermissionDenied("Only the owner can deactivate an owner account.")

    user.status = UserStatus.DEACTIVATED
    user.soft_delete()
    await db.commit()
    return Message(detail="Account deactivated. Their posts and comments stay put.")


# --------------------------------------------------------------------- roles
@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    db: DbSession, _: Annotated[User, require(Perm.USER_READ, Perm.ROLE_MANAGE)]
) -> list[Role]:
    rows = await db.scalars(select(Role).order_by(Role.priority.desc()))
    return list(rows.all())


@router.get("/permissions", response_model=list[PermissionInfo])
async def list_permissions(
    _: Annotated[User, require(Perm.ROLE_MANAGE)]
) -> list[PermissionInfo]:
    """The catalogue, grouped by resource, for the role editor."""
    return [
        PermissionInfo(
            name=name,
            description=PERMISSION_DESCRIPTIONS.get(name, ""),
            group=name.split(":")[0],
        )
        for name in ALL_PERMISSIONS
    ]


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: DbSession,
    actor: Annotated[User, require(Perm.ROLE_MANAGE)],
) -> Role:
    if await db.scalar(select(Role).where(Role.name == payload.name)):
        raise Conflict("A role with that name already exists.")
    unknown = set(payload.permissions) - set(ALL_PERMISSIONS)
    if unknown:
        raise ValidationFailed(f"Unknown permissions: {', '.join(sorted(unknown))}.")
    if payload.is_superuser and not actor.is_superuser:
        raise PermissionDenied("Only the owner can create a superuser role.")

    role = Role(**payload.model_dump())
    db.add(role)
    await db.commit()
    return role


@router.patch("/roles/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: DbSession,
    actor: Annotated[User, require(Perm.ROLE_MANAGE)],
) -> Role:
    role = await db.get(Role, role_id)
    if role is None:
        raise NotFound("No role with that id.")
    if role.is_superuser and not actor.is_superuser:
        raise PermissionDenied("Only the owner can change a superuser role.")

    data = payload.model_dump(exclude_unset=True)
    if "permissions" in data:
        unknown = set(data["permissions"]) - set(ALL_PERMISSIONS)
        if unknown:
            raise ValidationFailed(f"Unknown permissions: {', '.join(sorted(unknown))}.")
    for field, value in data.items():
        setattr(role, field, value)
    await db.commit()
    return role


@router.delete("/roles/{role_id}", response_model=Message)
async def delete_role(
    role_id: int, db: DbSession, _: Annotated[User, require(Perm.ROLE_MANAGE)]
) -> Message:
    role = await db.get(Role, role_id)
    if role is None:
        raise NotFound("No role with that id.")
    if role.is_system:
        raise ValidationFailed("Built-in roles cannot be deleted. Edit it instead.")
    await db.delete(role)
    await db.commit()
    return Message(detail="Role deleted.")
