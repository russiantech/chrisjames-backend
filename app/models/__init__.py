"""Importing this package registers every table on ``Base.metadata``."""

from app.db.base_class import Base
from app.models.advert import AdEvent, Advert, AdSlot, Sponsor
from app.models.comment import Comment, CommentReaction, CommentReport
from app.models.inbox import (
    ContactMessage,
    NewsletterCampaign,
    NewsletterSubscriber,
    ProjectRequest,
)
from app.models.media import MediaAsset
from app.models.notification import (
    EmailLog,
    Notification,
    NotificationPreference,
    WebhookEndpoint,
)
from app.models.payment import Payment, Plan, Subscription, WebhookEvent
from app.models.poll import Poll, PollOption, PollVote
from app.models.portfolio import (
    AuditLog,
    Experience,
    Project,
    Service,
    SiteSetting,
    Skill,
    SkillGroup,
    Testimonial,
)
from app.models.post import (
    Bookmark,
    ContentBlock,
    Post,
    PostReaction,
    PostRevision,
    PostView,
)
from app.models.taxonomy import Category, Series, Tag, post_tags
from app.models.user import RefreshToken, Role, User, user_roles

__all__ = [
    "Base",
    "AdEvent", "AdSlot", "Advert", "Sponsor",
    "Comment", "CommentReaction", "CommentReport",
    "ContactMessage", "NewsletterCampaign", "NewsletterSubscriber", "ProjectRequest",
    "MediaAsset",
    "EmailLog", "Notification", "NotificationPreference", "WebhookEndpoint",
    "Payment", "Plan", "Subscription", "WebhookEvent",
    "Poll", "PollOption", "PollVote",
    "AuditLog", "Experience", "Project", "Service", "SiteSetting",
    "Skill", "SkillGroup", "Testimonial",
    "Bookmark", "ContentBlock", "Post", "PostReaction", "PostRevision", "PostView",
    "Category", "Series", "Tag", "post_tags",
    "RefreshToken", "Role", "User", "user_roles",
]
