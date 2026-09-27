"""Enumerations shared by the ORM models and the Pydantic schemas."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "pending"        # registered, e-mail not yet verified
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class PostStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"    # waiting in the review queue
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class PostVisibility(StrEnum):
    PUBLIC = "public"
    UNLISTED = "unlisted"      # reachable by link, hidden from indexes
    MEMBERS = "members"        # signed-in readers only
    PRIVATE = "private"        # author and editors only


class BlockType(StrEnum):
    """Every content format a post body can hold.

    Blocks are ordered rows, each carrying a JSON ``data`` payload, so new
    formats can be added without a migration on the post table itself.
    """

    RICH_TEXT = "rich_text"
    MARKDOWN = "markdown"
    HEADING = "heading"
    CODE = "code"
    QUOTE = "quote"
    CALLOUT = "callout"
    LIST = "list"
    TABLE = "table"
    IMAGE = "image"
    GALLERY = "gallery"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    EMBED = "embed"            # YouTube, Vimeo, CodePen, X, Figma, Loom …
    POLL = "poll"
    QUIZ = "quiz"
    DIVIDER = "divider"
    BUTTON = "button"
    AD_SLOT = "ad_slot"
    HTML = "html"              # sanitised, admin-only
    MATH = "math"


class ModerationState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SPAM = "spam"
    HIDDEN = "hidden"


class ReactionType(StrEnum):
    LIKE = "like"
    LOVE = "love"
    INSIGHTFUL = "insightful"
    CELEBRATE = "celebrate"
    CURIOUS = "curious"
    DISLIKE = "dislike"


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    OTHER = "other"


class NotificationKind(StrEnum):
    COMMENT_ON_POST = "comment_on_post"
    REPLY_TO_COMMENT = "reply_to_comment"
    MENTION = "mention"
    REACTION = "reaction"
    POST_SUBMITTED = "post_submitted"
    POST_APPROVED = "post_approved"
    POST_REJECTED = "post_rejected"
    POST_PUBLISHED = "post_published"
    COMMENT_FLAGGED = "comment_flagged"
    CONTACT_MESSAGE = "contact_message"
    PROJECT_REQUEST = "project_request"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    AD_APPROVED = "ad_approved"
    AD_EXPIRING = "ad_expiring"
    NEWSLETTER = "newsletter"
    SYSTEM = "system"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class PollType(StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    RANKED = "ranked"
    RATING = "rating"


class RequestStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    IN_DISCUSSION = "in_discussion"
    QUOTED = "quoted"
    WON = "won"
    LOST = "lost"
    ARCHIVED = "archived"


class MessageStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"
    REPLIED = "replied"
    SPAM = "spam"
    ARCHIVED = "archived"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELLED = "cancelled"


class PaymentPurpose(StrEnum):
    ADVERT = "advert"
    PROJECT_DEPOSIT = "project_deposit"
    SUBSCRIPTION = "subscription"
    SPONSORSHIP = "sponsorship"
    TIP = "tip"
    OTHER = "other"


class AdStatus(StrEnum):
    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    PENDING_REVIEW = "pending_review"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"


class AdPricingModel(StrEnum):
    CPM = "cpm"
    CPC = "cpc"
    FLAT_DAILY = "flat_daily"
    FLAT_WEEKLY = "flat_weekly"
    FLAT_MONTHLY = "flat_monthly"


class SubscriberStatus(StrEnum):
    PENDING = "pending"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
