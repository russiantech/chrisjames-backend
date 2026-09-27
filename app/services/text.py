"""Markdown rendering, HTML sanitising, slugs, excerpts and reading time."""

from __future__ import annotations

import re
from typing import Iterable

import bleach
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound
from slugify import slugify as _slugify

# --------------------------------------------------------------- sanitising
#: Tags a comment author may use. Deliberately narrow.
COMMENT_TAGS = [
    "p", "br", "strong", "em", "del", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "h3", "h4", "hr", "span", "div", "table",
    "thead", "tbody", "tr", "th", "td", "img", "sup", "sub",
    # emitted by the code-block highlighter
    "figure", "figcaption", "button",
]

#: Tags an editor may use in a rich_text or callout block.
POST_TAGS = COMMENT_TAGS + [
    "h2", "h5", "h6", "figure", "figcaption", "iframe", "video", "audio",
    "source", "track", "small", "mark", "kbd", "abbr", "dl", "dt", "dd",
]

COMMON_ATTRS = {
    "*": ["class", "id", "data-lang", "data-line"],
    "button": ["type", "data-copy"],
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "video": ["src", "poster", "controls", "width", "height", "preload"],
    "audio": ["src", "controls", "preload"],
    "source": ["src", "type", "srcset"],
    "track": ["src", "kind", "srclang", "label", "default"],
    "iframe": ["src", "title", "allow", "allowfullscreen", "loading", "frameborder"],
    "abbr": ["title"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
}

SAFE_PROTOCOLS = ["http", "https", "mailto", "data"]

#: Hosts an iframe may point at. Anything else is stripped.
EMBED_ALLOWLIST = {
    "www.youtube.com", "youtube.com", "www.youtube-nocookie.com",
    "player.vimeo.com", "codepen.io", "codesandbox.io",
    "open.spotify.com", "w.soundcloud.com", "platform.twitter.com",
    "www.figma.com", "www.loom.com", "gist.github.com",
    "anchor.fm", "share.transistor.fm",
}

_md = (
    MarkdownIt("commonmark", {"breaks": True, "linkify": True, "html": False})
    .enable("table")
    .enable("strikethrough")
)

_MENTION_RE = re.compile(r"(?<![\w/])@([a-z0-9][a-z0-9._-]{2,29})", re.IGNORECASE)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean(html: str, tags: Iterable[str]) -> str:
    cleaned = bleach.clean(
        html,
        tags=set(tags),
        attributes=COMMON_ATTRS,
        protocols=SAFE_PROTOCOLS,
        strip=True,
    )
    return _strip_untrusted_iframes(cleaned)


def _strip_untrusted_iframes(html: str) -> str:
    """Remove iframes whose ``src`` host is not on the embed allowlist."""

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        if not src:
            return ""
        host = re.sub(r"^https?://", "", src.group(1)).split("/")[0].lower()
        return tag if host in EMBED_ALLOWLIST else ""

    return re.sub(r"<iframe\b[^>]*>(?:</iframe>)?", repl, html, flags=re.IGNORECASE)


def sanitize_comment_html(html: str) -> str:
    return _clean(html, COMMENT_TAGS)


def sanitize_post_html(html: str) -> str:
    return _clean(html, POST_TAGS)


# ----------------------------------------------------------------- rendering
def render_markdown(source: str, *, trusted: bool = False) -> str:
    """Markdown → sanitised HTML, with fenced code blocks highlighted."""
    raw = _md.render(source or "")
    raw = _highlight_fenced_blocks(raw)
    return sanitize_post_html(raw) if trusted else sanitize_comment_html(raw)


def _highlight_fenced_blocks(html: str) -> str:
    """Replace ``<pre><code class="language-x">`` bodies with Pygments output."""

    def repl(match: re.Match[str]) -> str:
        language = match.group(1) or "text"
        body = bleach.clean(match.group(2), tags=set(), strip=True)
        import html as _html

        return highlight_code(_html.unescape(body), language)

    return re.sub(
        r'<pre><code(?: class="language-([^"]+)")?>(.*?)</code></pre>',
        repl,
        html,
        flags=re.DOTALL,
    )


def highlight_code(
    source: str,
    language: str = "text",
    *,
    filename: str | None = None,
    line_numbers: bool = True,
    highlight_lines: list[int] | None = None,
) -> str:
    """Render a code block as themed HTML.

    Uses the ``cj-code`` CSS class set, which is styled to sit inside the
    existing Webpixels surface tokens rather than shipping a Pygments theme.
    """
    try:
        lexer = get_lexer_by_name(language, stripall=False)
    except ClassNotFound:
        try:
            lexer = guess_lexer(source)
        except ClassNotFound:
            lexer = get_lexer_by_name("text")

    formatter = HtmlFormatter(
        nowrap=False,
        cssclass="cj-code__body",
        linenos="table" if line_numbers else False,
        hl_lines=highlight_lines or [],
        wrapcode=True,
    )
    body = highlight(source, lexer, formatter)
    label = filename or lexer.name
    return (
        f'<figure class="cj-code" data-lang="{bleach.clean(language)}">'
        f'<figcaption class="cj-code__bar">'
        f'<span class="cj-code__name">{bleach.clean(label)}</span>'
        f'<button type="button" class="cj-code__copy" data-copy>Copy</button>'
        f"</figcaption>{body}</figure>"
    )


def pygments_stylesheet(style: str = "default") -> str:
    return HtmlFormatter(style=style, cssclass="cj-code__body").get_style_defs()


# ------------------------------------------------------------------- helpers
def slugify(value: str, max_length: int = 120) -> str:
    return _slugify(value, max_length=max_length) or "untitled"


def extract_mentions(text: str) -> list[str]:
    return sorted({m.group(1).lower() for m in _MENTION_RE.finditer(text or "")})


def linkify_mentions(html: str, base: str = "/u/") -> str:
    return _MENTION_RE.sub(
        lambda m: f'<a class="cj-mention" href="{base}{m.group(1).lower()}">@{m.group(1)}</a>',
        html,
    )


def to_plain_text(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_STRIP_RE.sub(" ", html or "")).strip()


def word_count(text: str) -> int:
    return len([w for w in _WS_RE.split(to_plain_text(text)) if w])


def reading_minutes(words: int, wpm: int = 225) -> int:
    return max(1, round(words / wpm)) if words else 1


def build_excerpt(text: str, limit: int = 220) -> str:
    plain = to_plain_text(text)
    if len(plain) <= limit:
        return plain
    cut = plain[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"
