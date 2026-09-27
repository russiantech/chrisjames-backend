"""Permission catalogue and the default role → permission mapping.

Permissions are plain strings of the form ``<resource>:<action>``. Roles are
rows in the database, so an administrator can invent new roles at runtime; the
constants below only seed the initial set.
"""

from __future__ import annotations

from enum import StrEnum


class Perm(StrEnum):
    # content -----------------------------------------------------------
    POST_READ_DRAFT = "post:read_draft"
    POST_CREATE = "post:create"
    POST_EDIT_OWN = "post:edit_own"
    POST_EDIT_ANY = "post:edit_any"
    POST_DELETE_OWN = "post:delete_own"
    POST_DELETE_ANY = "post:delete_any"
    POST_PUBLISH = "post:publish"          # bypasses the review queue
    POST_MODERATE = "post:moderate"        # approve / reject submissions
    POST_FEATURE = "post:feature"

    # comments ----------------------------------------------------------
    COMMENT_CREATE = "comment:create"
    COMMENT_EDIT_OWN = "comment:edit_own"
    COMMENT_DELETE_OWN = "comment:delete_own"
    COMMENT_MODERATE = "comment:moderate"

    # media -------------------------------------------------------------
    MEDIA_UPLOAD = "media:upload"
    MEDIA_DELETE_OWN = "media:delete_own"
    MEDIA_DELETE_ANY = "media:delete_any"

    # taxonomy ----------------------------------------------------------
    TAXONOMY_MANAGE = "taxonomy:manage"

    # portfolio (projects, experience, services, testimonials) ----------
    PORTFOLIO_MANAGE = "portfolio:manage"

    # inbox (contact messages, project requests) ------------------------
    INBOX_READ = "inbox:read"
    INBOX_RESPOND = "inbox:respond"

    # newsletter --------------------------------------------------------
    NEWSLETTER_MANAGE = "newsletter:manage"

    # adverts -----------------------------------------------------------
    AD_MANAGE = "ad:manage"
    AD_PURCHASE = "ad:purchase"

    # payments ----------------------------------------------------------
    PAYMENT_READ = "payment:read"
    PAYMENT_REFUND = "payment:refund"

    # people ------------------------------------------------------------
    USER_READ = "user:read"
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"

    # platform ----------------------------------------------------------
    SETTINGS_MANAGE = "settings:manage"
    ANALYTICS_READ = "analytics:read"
    AUDIT_READ = "audit:read"


ALL_PERMISSIONS: tuple[str, ...] = tuple(p.value for p in Perm)

PERMISSION_DESCRIPTIONS: dict[str, str] = {
    Perm.POST_READ_DRAFT: "View drafts and posts awaiting review",
    Perm.POST_CREATE: "Write new blog posts",
    Perm.POST_EDIT_OWN: "Edit posts they authored",
    Perm.POST_EDIT_ANY: "Edit anybody's post",
    Perm.POST_DELETE_OWN: "Delete posts they authored",
    Perm.POST_DELETE_ANY: "Delete anybody's post",
    Perm.POST_PUBLISH: "Publish straight away, skipping review",
    Perm.POST_MODERATE: "Approve or reject submitted posts",
    Perm.POST_FEATURE: "Pin posts to the featured rail",
    Perm.COMMENT_CREATE: "Leave comments and replies",
    Perm.COMMENT_EDIT_OWN: "Edit their own comments",
    Perm.COMMENT_DELETE_OWN: "Delete their own comments",
    Perm.COMMENT_MODERATE: "Approve, hide or delete any comment",
    Perm.MEDIA_UPLOAD: "Upload images, video, audio and files",
    Perm.MEDIA_DELETE_OWN: "Delete their own uploads",
    Perm.MEDIA_DELETE_ANY: "Delete anybody's upload",
    Perm.TAXONOMY_MANAGE: "Manage categories, tags and series",
    Perm.PORTFOLIO_MANAGE: "Edit projects, experience, services and testimonials",
    Perm.INBOX_READ: "Read contact messages and project requests",
    Perm.INBOX_RESPOND: "Reply to contact messages and project requests",
    Perm.NEWSLETTER_MANAGE: "Manage subscribers and send campaigns",
    Perm.AD_MANAGE: "Manage advert slots, creatives and billing",
    Perm.AD_PURCHASE: "Buy an advert placement",
    Perm.PAYMENT_READ: "View payments and invoices",
    Perm.PAYMENT_REFUND: "Issue refunds",
    Perm.USER_READ: "View the people directory",
    Perm.USER_MANAGE: "Create, suspend and edit accounts",
    Perm.ROLE_MANAGE: "Create roles and assign permissions",
    Perm.SETTINGS_MANAGE: "Change site-wide settings",
    Perm.ANALYTICS_READ: "View traffic and engagement analytics",
    Perm.AUDIT_READ: "Read the audit trail",
}


AUTHOR_PERMS: tuple[str, ...] = (
    Perm.POST_READ_DRAFT, Perm.POST_CREATE, Perm.POST_EDIT_OWN,
    Perm.POST_DELETE_OWN, Perm.COMMENT_CREATE, Perm.COMMENT_EDIT_OWN,
    Perm.COMMENT_DELETE_OWN, Perm.MEDIA_UPLOAD, Perm.MEDIA_DELETE_OWN,
)

EDITOR_PERMS: tuple[str, ...] = AUTHOR_PERMS + (
    Perm.POST_EDIT_ANY, Perm.POST_PUBLISH, Perm.POST_MODERATE, Perm.POST_FEATURE,
    Perm.COMMENT_MODERATE, Perm.TAXONOMY_MANAGE, Perm.MEDIA_DELETE_ANY,
    Perm.NEWSLETTER_MANAGE, Perm.ANALYTICS_READ,
)

DEFAULT_ROLES: dict[str, dict[str, object]] = {
    "owner": {
        "label": "Owner",
        "description": "Christopher. Unrestricted access to everything.",
        "is_superuser": True,
        "permissions": list(ALL_PERMISSIONS),
        "priority": 100,
    },
    "admin": {
        "label": "Administrator",
        "description": "Runs the site day to day; everything except role deletion of the owner.",
        "is_superuser": False,
        "permissions": list(ALL_PERMISSIONS),
        "priority": 90,
    },
    "editor": {
        "label": "Editor",
        "description": "Reviews the queue, publishes, and curates the blog.",
        "is_superuser": False,
        "permissions": list(EDITOR_PERMS),
        "priority": 70,
    },
    "author": {
        "label": "Author",
        "description": "Team member who writes posts; publishing goes through review.",
        "is_superuser": False,
        "permissions": list(AUTHOR_PERMS),
        "priority": 50,
    },
    "contributor": {
        "label": "Contributor",
        "description": "Registered visitor who may submit a post for review.",
        "is_superuser": False,
        "permissions": [
            Perm.POST_CREATE, Perm.POST_EDIT_OWN, Perm.POST_DELETE_OWN,
            Perm.COMMENT_CREATE, Perm.COMMENT_EDIT_OWN, Perm.COMMENT_DELETE_OWN,
            Perm.MEDIA_UPLOAD, Perm.MEDIA_DELETE_OWN,
        ],
        "priority": 30,
    },
    "advertiser": {
        "label": "Advertiser",
        "description": "Buys and manages advert placements.",
        "is_superuser": False,
        "permissions": [Perm.AD_PURCHASE, Perm.COMMENT_CREATE, Perm.MEDIA_UPLOAD],
        "priority": 20,
    },
    "member": {
        "label": "Member",
        "description": "Signed-in reader. Comments, votes in polls, bookmarks.",
        "is_superuser": False,
        "permissions": [
            Perm.COMMENT_CREATE, Perm.COMMENT_EDIT_OWN, Perm.COMMENT_DELETE_OWN,
        ],
        "priority": 10,
    },
}

DEFAULT_SIGNUP_ROLE = "member"
