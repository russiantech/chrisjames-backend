"""Outbound e-mail.

Every message is written to the ``email_logs`` table first, then handed to
SMTP. With ``EMAIL_DRY_RUN`` on (the default in development) the SMTP step is
skipped and the row is marked ``dry_run``, so the whole notification system can
be exercised without a mail server.
"""

from __future__ import annotations

import asyncio
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import EmailLog
from app.services.text import to_plain_text

# --------------------------------------------------------------- templates
#: Minimal inline-styled shell so mail matches the site without a build step.
_SHELL = """\
<div style="background:#f5f9fc;padding:32px 0;font-family:Inter,Segoe UI,Arial,sans-serif">
  <div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e7eaf0;border-radius:16px;overflow:hidden">
    <div style="padding:24px 28px;border-bottom:1px solid #e7eaf0">
      <span style="font-size:18px;font-weight:700;color:#16192c">{owner}</span>
    </div>
    <div style="padding:28px;color:#525f7f;font-size:15px;line-height:1.6">{body}</div>
    <div style="padding:18px 28px;border-top:1px solid #e7eaf0;font-size:12px;color:#8898a9">
      {footer}
    </div>
  </div>
</div>"""

_BUTTON = (
    '<p style="margin:24px 0"><a href="{url}" style="display:inline-block;'
    "background:#5826ee;color:#fff;text-decoration:none;padding:12px 22px;"
    'border-radius:999px;font-weight:600">{label}</a></p>'
)

TEMPLATES: dict[str, dict[str, str]] = {
    "verify_email": {
        "subject": "Confirm your e-mail address",
        "body": "<p>Hi {name},</p><p>Confirm this address to finish setting up your account.</p>"
                + _BUTTON.format(url="{action_url}", label="Confirm e-mail"),
    },
    "reset_password": {
        "subject": "Reset your password",
        "body": "<p>Hi {name},</p><p>Use the link below to choose a new password. "
                "It stops working in {minutes} minutes.</p>"
                + _BUTTON.format(url="{action_url}", label="Choose a new password")
                + "<p>If you did not ask for this, ignore the message — nothing changes.</p>",
    },
    "welcome": {
        "subject": "Welcome aboard",
        "body": "<p>Hi {name},</p><p>Your account is live. You can comment, vote in polls "
                "and submit posts for review.</p>"
                + _BUTTON.format(url="{action_url}", label="Open the site"),
    },
    "contact_ack": {
        "subject": "Thanks — your message landed",
        "body": "<p>Hi {name},</p><p>Your message reached my inbox and I read every one. "
                "Expect a reply within two working days.</p>"
                "<blockquote style='border-left:3px solid #e7eaf0;margin:16px 0;padding-left:14px;color:#6b7b93'>{excerpt}</blockquote>",
    },
    "contact_admin": {
        "subject": "New message: {subject}",
        "body": "<p><strong>{name}</strong> &lt;{email}&gt; wrote:</p><p>{excerpt}</p>"
                + _BUTTON.format(url="{action_url}", label="Open in dashboard"),
    },
    "request_ack": {
        "subject": "Your project brief — reference {reference}",
        "body": "<p>Hi {name},</p><p>Thanks for the brief on <strong>{project_title}</strong>. "
                "I will come back with questions or a scoped proposal shortly.</p>"
                "<p>Your reference is <strong>{reference}</strong>.</p>",
    },
    "request_admin": {
        "subject": "New project brief: {project_title}",
        "body": "<p><strong>{name}</strong> ({company}) submitted a brief.</p>"
                "<p>Budget: {budget} · Timeline: {timeline}</p>"
                + _BUTTON.format(url="{action_url}", label="Review the brief"),
    },
    "post_submitted": {
        "subject": "A post is waiting for review",
        "body": "<p><strong>{author}</strong> submitted <strong>{title}</strong>.</p>"
                + _BUTTON.format(url="{action_url}", label="Review the post"),
    },
    "post_approved": {
        "subject": "Your post is live",
        "body": "<p>Hi {name},</p><p><strong>{title}</strong> has been published.</p>"
                + _BUTTON.format(url="{action_url}", label="Read it"),
    },
    "post_rejected": {
        "subject": "Your post needs changes",
        "body": "<p>Hi {name},</p><p><strong>{title}</strong> was not published.</p>"
                "<p>{reason}</p><p>Edit it and submit again whenever you are ready.</p>",
    },
    "comment_reply": {
        "subject": "{actor} replied to you",
        "body": "<p><strong>{actor}</strong> replied on <strong>{title}</strong>:</p>"
                "<blockquote style='border-left:3px solid #e7eaf0;margin:16px 0;padding-left:14px;color:#6b7b93'>{excerpt}</blockquote>"
                + _BUTTON.format(url="{action_url}", label="View the thread"),
    },
    "payment_receipt": {
        "subject": "Receipt for {description}",
        "body": "<p>Hi {name},</p><p>Payment of <strong>{amount}</strong> received.</p>"
                "<p>Reference: {reference}</p>",
    },
    "newsletter_confirm": {
        "subject": "Confirm your subscription",
        "body": "<p>One click and you are on the list.</p>"
                + _BUTTON.format(url="{action_url}", label="Confirm subscription"),
    },
    "generic": {"subject": "{subject}", "body": "{body}"},
}


def render_template(name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Return ``(subject, html)`` for a template name and context."""
    template = TEMPLATES.get(name, TEMPLATES["generic"])
    safe = {k: ("" if v is None else str(v)) for k, v in context.items()}

    def fill(text: str) -> str:
        try:
            return text.format(**safe)
        except (KeyError, IndexError):
            # A missing placeholder should never lose the message.
            for key, value in safe.items():
                text = text.replace("{" + key + "}", value)
            return text

    subject = fill(template["subject"])
    body = _SHELL.format(
        owner=settings.OWNER_NAME,
        body=fill(template["body"]),
        footer=safe.get(
            "footer",
            f'<a href="{settings.SITE_URL}" style="color:#8898a9">{settings.SITE_URL}</a>',
        ),
    )
    return subject, body


# ------------------------------------------------------------------ sending
def _send_smtp(to_address: str, subject: str, html: str, text: str) -> None:
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST or "localhost", settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_TLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
        smtp.send_message(message)


async def send_email(
    db: AsyncSession,
    *,
    to_address: str,
    template: str = "generic",
    context: dict[str, Any] | None = None,
    subject: str | None = None,
    html: str | None = None,
) -> EmailLog:
    """Queue, log and (unless dry-run) deliver one message."""
    context = context or {}
    rendered_subject, rendered_html = render_template(template, context)
    subject = subject or rendered_subject
    html = html or rendered_html
    text = to_plain_text(html)

    log = EmailLog(
        to_address=to_address,
        from_address=settings.EMAIL_FROM,
        subject=subject[:300],
        template=template,
        body_html=html,
        body_text=text,
        context=context,
        status="queued",
    )
    db.add(log)
    await db.flush()

    dry_run = settings.EMAIL_DRY_RUN or not settings.SMTP_HOST
    if dry_run:
        log.status = "dry_run"
        log.sent_at = datetime.now(timezone.utc)
        log.attempts = 1
        return log

    try:
        await asyncio.to_thread(_send_smtp, to_address, subject, html, text)
        log.status = "sent"
        log.sent_at = datetime.now(timezone.utc)
    except Exception as exc:  # pragma: no cover - network dependent
        log.status = "failed"
        log.error = str(exc)[:2000]
    finally:
        log.attempts += 1
    return log
