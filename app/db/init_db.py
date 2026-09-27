"""Schema creation and first-run seeding."""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.permissions import DEFAULT_ROLES
from app.core.security import hash_password
from app.db.session import engine, session_scope
from app.models import Base
from app.models.advert import AdSlot, Sponsor
from app.models.enums import (
    AdPricingModel,
    BlockType,
    PostStatus,
    UserStatus,
)
from app.models.payment import Plan
from app.models.portfolio import (
    Experience,
    Project,
    Service,
    Skill,
    SkillGroup,
    Testimonial,
)
from app.models.post import ContentBlock, Post
from app.models.taxonomy import Category, Tag
from app.models.user import Role, User
from app.services.posts import normalise_block, recompute_metrics
from app.schemas.post import ContentBlockIn

logger = logging.getLogger(__name__)


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_roles(db) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name, spec in DEFAULT_ROLES.items():
        role = await db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(
                name=name,
                label=spec["label"],
                description=spec["description"],
                permissions=list(spec["permissions"]),
                is_superuser=bool(spec["is_superuser"]),
                priority=int(spec["priority"]),
                is_system=True,
            )
            db.add(role)
        else:
            # Keep built-in roles current as the permission catalogue grows.
            role.permissions = list(spec["permissions"])
            role.label = spec["label"]
        roles[name] = role
    await db.flush()
    return roles


async def seed_owner(db, roles: dict[str, Role]) -> User:
    owner = await db.scalar(
        select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL.lower())
    )
    if owner is not None:
        return owner

    owner = User(
        email=settings.FIRST_SUPERUSER_EMAIL.lower(),
        username=settings.FIRST_SUPERUSER_USERNAME,
        full_name=settings.OWNER_NAME,
        hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
        status=UserStatus.ACTIVE,
        email_verified_at=datetime.now(timezone.utc),
        headline="Full-stack software engineer — AI, SaaS and product engineering",
        bio=(
            "Full-stack software engineer with 5+ years building web platforms, SaaS "
            "products, internal business systems and AI-integrated applications. I work "
            "across the full product lifecycle — architecture, API design, frontend, "
            "deployment, integrations and ongoing optimisation — and have led engineering "
            "initiatives across e-commerce, education, workforce management and vertical SaaS."
        ),
        location="Lagos, Nigeria",
        social_links={
            "github": "https://github.com/russiantech",
            "linkedin": "https://www.linkedin.com/in/chrisjsm",
            "x": "https://twitter.com/chris_jsmes",
            "portfolio": "https://chris-james.vercel.app",
        },
    )
    owner.roles = [roles["owner"]]
    db.add(owner)
    await db.flush()
    logger.info("Created owner account: %s", owner.email)
    return owner


SERVICES = [
    (
        "Custom software",
        "bi-code-slash",
        "primary",
        "Web platforms and internal tools built to fit the way your business actually works.",
        ["Discovery and technical scoping", "Design system and build", "Deployment, monitoring and handover"],
        350000,
    ),
    (
        "AI and data",
        "bi-cpu",
        "warning",
        "Models and pipelines that earn their keep — search, forecasting, classification, retrieval.",
        ["Data audit and feasibility", "Model training and evaluation", "Serving, monitoring and retraining"],
        450000,
    ),
    (
        "Business automation",
        "bi-gear-wide-connected",
        "success",
        "Take the repetitive work out of the day. Integrations, workflows, scheduled jobs.",
        ["Process mapping", "Integration with the tools you already pay for", "Reporting and alerting"],
        200000,
    ),
    (
        "Security review",
        "bi-shield-check",
        "danger",
        "Find the holes before somebody else does. Application, infrastructure and access review.",
        ["Threat model and attack surface", "Authenticated testing", "Written findings with fixes"],
        280000,
    ),
]

PROJECTS = [
    {
        "title": "Salesnet",
        "tagline": "Internet of Sales — a Lagos-first marketplace",
        "summary": (
            "AI-powered marketplace connecting local vendors and buyers through free "
            "digital storefronts, intelligent product discovery, local pricing insight, "
            "geo-location vendor recommendations and embedded fintech."
        ),
        "kind": "product", "role": "Founder & Lead Engineer", "accent": "warning",
        "icon": "bi-cart", "cover_url": "/assets/img/salesnet.png",
        "stack": ["Python", "FastAPI", "React", "PostgreSQL", "Redis"],
        "highlights": [
            "Free vendor storefronts with AI-driven local pricing and tagging",
            "Geo-location vendor recommendations",
            "Embedded fintech; AR try-on for wearables on the roadmap",
        ],
        "live_url": "https://techa.salesnet.ng",
        "is_featured": True, "position": 0,
    },
    {
        "title": "Intellect",
        "tagline": "Your digital learning companion",
        "summary": (
            "Digital learning platform with video, PDF, PowerPoint, audio and interactive "
            "lessons, an AI learning assistant, auto-certificates, live sessions and a "
            "Creator Studio for monetisation."
        ),
        "kind": "product", "role": "Founder & Lead Developer", "accent": "primary",
        "icon": "bi-mortarboard", "cover_url": "/assets/img/intellect.png",
        "stack": ["Python", "FastAPI", "React", "PostgreSQL"],
        "highlights": [
            "AI-assisted learning and auto-generated certificates",
            "Live sessions alongside recorded, downloadable content",
            "Creator Studio for monetisation and B2B learning partnerships",
        ],
        "live_url": "https://intellect.salesnet.ng",
        "is_featured": True, "position": 1,
    },
    {
        "title": "Stitch",
        "tagline": "Vertical SaaS for Nigeria's laundry and fashion economy",
        "summary": (
            "Digitises SME operations through order management, workflow tracking, "
            "inventory management, service management, customer management and "
            "embedded payments — turning notebook operations into predictable revenue."
        ),
        "kind": "product", "role": "Lead Engineer", "accent": "success",
        "icon": "bi-basket", "cover_url": None,
        "stack": ["Python", "FastAPI", "React", "PostgreSQL", "Supabase"],
        "highlights": [
            "Order and workflow tracking built for informal SMEs",
            "Inventory and customer management in one place",
            "Embedded payments replacing paper ledgers",
        ],
        "live_url": "https://stitch.salesnet.ng",
        "is_featured": True, "position": 2,
    },
    {
        "title": "Score App",
        "tagline": "Academic scoring and performance management",
        "summary": (
            "Built for Dunistech Academy and partner institutions. Tracks attendance, "
            "records and manages scores, keeps parents informed with automated updates, "
            "and auto-generates performance analysis."
        ),
        "kind": "client", "role": "Lead Engineer", "accent": "info",
        "icon": "bi-clipboard-data", "cover_url": None,
        "stack": ["Python", "FastAPI", "React"],
        "highlights": [
            "Automated parent updates on attendance and scores",
            "Auto-generated performance analysis and insights",
        ],
        "is_featured": False, "position": 3,
    },
    {
        "title": "Dunis Inventory",
        "tagline": "Precision inventory and profit analytics for SME retailers",
        "summary": (
            "Real-time stock tracking, sales reporting, demand forecasting and financial "
            "insight — built for SME retailers and commercialised by Dunis Technologies."
        ),
        "kind": "product", "role": "Lead Developer", "accent": "danger",
        "icon": "bi-boxes", "cover_url": None,
        "stack": ["Python", "FastAPI", "React", "PostgreSQL"],
        "highlights": [
            "Real-time stock tracking with sales reporting",
            "Demand forecasting and profit analytics",
        ],
        "is_featured": False, "position": 4,
    },
    {
        "title": "Techa",
        "tagline": "Personal engineering portfolio and SaaS launchpad",
        "summary": (
            "The site you are looking at right now — a central hub for product demos, "
            "technical writing and client project showcases."
        ),
        "kind": "personal", "role": "Founder & Lead Engineer", "accent": "secondary",
        "icon": "bi-rocket-takeoff", "cover_url": "/assets/img/techa_hero.png",
        "stack": ["Python", "FastAPI", "React", "TypeScript"],
        "highlights": [
            "Full blog CMS with polls, code blocks, video and audio",
            "Role-based publishing with a visitor-submission review queue",
        ],
        "live_url": "https://techa.salesnet.ng",
        "is_featured": False, "position": 5,
    },
]


async def seed_portfolio(db) -> None:
    if await db.scalar(select(Service.id).limit(1)):
        return

    from app.services.text import slugify

    for position, (title, icon, accent, summary, bullets, price) in enumerate(SERVICES):
        db.add(
            Service(
                title=title, slug=slugify(title), summary=summary, icon=icon,
                accent=accent, bullets=bullets, starting_price_minor=price,
                position=position,
            )
        )

    for spec in PROJECTS:
        db.add(Project(**spec, slug=slugify(spec["title"]), state="live"))

    # NOTE: Dunis and Kovun list no explicit start month on the source résumé
    # (both read "Present" only) — 2023-01-01 is a placeholder start date.
    # Correct it from the dashboard once the real month is known.
    db.add_all([
        Experience(
            organisation="Dunis Technologies Limited", title="Lead Technical Engineer (Software)",
            location="Lagos, Nigeria", employment_type="full_time",
            started_on=date(2023, 1, 1), is_current=True,
            summary="Architecting and deploying internal platforms and client-facing solutions for Dunis and its clients.",
            achievements=[
                "Built Workforce, a staffing, attendance and compliance platform used internally",
                "Built Dunis Inventory, a real-time stock tracking and profit analytics SaaS commercialised by Dunis",
                "Built Score App for Dunistech Academy — attendance, scoring and automated parent updates",
                "Built SimplyLovely Laundry, an operations management app for laundry workflows",
                "Train software engineering students and staff in modern development practices",
            ],
            stack=["Python", "FastAPI", "React", "PostgreSQL"], position=0,
        ),
        Experience(
            organisation="Kovun Academy", title="Lead Full-Stack Engineer",
            location="Remote", employment_type="full_time",
            started_on=date(2023, 6, 1), is_current=True,
            summary="Architected and deployed a full-featured online video learning platform.",
            achievements=[
                "Video streaming, live sessions, auto-certificates and AI-powered learning assistance",
                "Led a cross-functional team; established CI/CD pipelines and code review standards",
                "Built payment and subscription flows for digital learning products",
            ],
            stack=["Python", "React", "PostgreSQL", "CI/CD"], position=1,
        ),
        Experience(
            organisation="Bizalert", title="Software Engineer",
            location="Lekki, Lagos", employment_type="full_time",
            started_on=date(2021, 4, 1), is_current=True,
            summary="Client-facing web applications for a marketing and technology agency.",
            achievements=[
                "Designed and deployed client-facing web apps using JavaScript, jQuery, Python/Flask and REST APIs",
                "Built internal analytics dashboards for campaign performance and conversion tracking",
            ],
            stack=["Python", "Flask", "JavaScript", "jQuery"], position=2,
        ),
        Experience(
            organisation="Jobilate", title="Digital Marketing Specialist",
            location="Sangotedo, Lagos", employment_type="full_time",
            started_on=date(2018, 2, 1), ended_on=date(2018, 5, 31), is_current=False,
            summary="Paid campaigns and SEO to grow audience engagement and brand visibility.",
            achievements=[
                "Executed paid ad and SEO campaigns to increase engagement and visibility",
                "Implemented analytics tooling to track visitor behaviour and optimise conversion funnels",
            ],
            stack=[], position=3,
        ),
        # Education, reusing the same table — employment_type="education" is
        # how the About page tells the two groups apart.
        Experience(
            organisation="ALX Software Engineering Program", title="Professional Certification — Full-Stack Software Engineering",
            location="Nairobi, Kenya (Remote)", employment_type="education",
            started_on=date(2022, 4, 1), ended_on=date(2024, 9, 30), is_current=False,
            summary="Professional certification programme in full-stack software engineering.",
            achievements=[], stack=[], position=10,
        ),
        Experience(
            organisation="Miva Open University", title="B.Sc. Computer Science",
            location="Nigeria", employment_type="education",
            started_on=date(2023, 1, 1), is_current=True,
            summary="In progress.",
            achievements=[], stack=[], position=11,
        ),
        Experience(
            organisation="Dunis Technologies Limited", title="Certification — Software Programming (Python & JavaScript)",
            location="Lagos, Nigeria", employment_type="education",
            started_on=date(2022, 1, 1), is_current=False,
            summary="Certification in software programming.",
            achievements=[], stack=[], position=12,
        ),
    ])

    groups = [
        ("Backend", "bi-hdd-stack", "primary", ["Python", "FastAPI", "Django", "Flask", "Node.js (Express)", "PHP"]),
        ("Frontend", "bi-window", "info", ["React", "TypeScript", "JavaScript", "Bootstrap", "Tailwind"]),
        ("Data & storage", "bi-database", "warning", ["PostgreSQL", "MySQL", "MongoDB", "Supabase", "Redis"]),
        ("Engineering", "bi-gear-wide-connected", "success",
         ["REST APIs", "Auth", "Payment integrations", "AI/LLM integration", "CI/CD", "Cloud deployment"]),
    ]
    for position, (name, icon, accent, skills) in enumerate(groups):
        group = SkillGroup(name=name, icon=icon, accent=accent, position=position)
        group.skills = [
            Skill(name=skill_name, level=5 - (skill_position // 3), position=skill_position)
            for skill_position, skill_name in enumerate(skills)
        ]
        db.add(group)

    db.add_all([
        Testimonial(
            author_name="Adaeze Okonkwo", author_title="Operations director",
            author_company="Lagos Logistics",
            quote="He rebuilt our dispatch system in six weeks. It has not gone down once since, and we stopped losing an hour a day to manual reconciliation.",
            is_featured=True, position=0,
        ),
        Testimonial(
            author_name="Marcus Feld", author_title="CTO", author_company="Northgate",
            quote="Clear scoping, no surprises, and the handover documentation was better than what our own team writes.",
            is_featured=True, position=1,
        ),
    ])

    db.add_all([
        Sponsor(name="Coinbase", logo_url="/assets/img/coinbase.png", position=0),
        Sponsor(name="Google", logo_url="/assets/img/google.png", position=1),
        Sponsor(name="Y Combinator", logo_url="/assets/img/y-combinator.png", position=2),
        Sponsor(name="Speckyboy", logo_url="/assets/img/speckyboy.png", position=3),
        Sponsor(name="Bizoo", logo_url="/assets/img/bizoo-dark.png", position=4),
        Sponsor(name="Oblio", logo_url="/assets/img/oblio-dark.png", position=5),
    ])


async def seed_commerce(db) -> None:
    if await db.scalar(select(Plan.id).limit(1)):
        return

    db.add_all([
        Plan(
            name="Discovery call", slug="discovery", family="engagement",
            amount_minor=0, interval="one_time", position=0,
            description="A 45-minute call to work out whether this is a fit.",
            features=["45 minutes", "Written summary afterwards", "No obligation"],
        ),
        Plan(
            name="Project sprint", slug="sprint", family="engagement",
            amount_minor=350000, interval="one_time", position=1, is_highlighted=True,
            badge="Most booked",
            description="Two weeks of focused build on a scoped piece of work.",
            features=["Two-week sprint", "Daily written updates", "Working software at the end", "Two weeks of support"],
            entitlements={"support_days": 14},
        ),
        Plan(
            name="Retainer", slug="retainer", family="engagement",
            amount_minor=900000, interval="monthly", position=2,
            description="Ongoing engineering capacity, month to month.",
            features=["60 hours a month", "Same-day response", "Architecture review", "Cancel any time"],
            entitlements={"hours": 60, "response_hours": 8},
        ),
    ])

    db.add_all([
        AdSlot(
            key="sidebar_primary", name="Blog sidebar", placement="sidebar",
            format="300x250", width=300, height=250,
            pricing_model=AdPricingModel.FLAT_MONTHLY, base_price_minor=40000,
            fallback_html='<div class="text-center p-4"><p class="text-sm text-muted mb-2">This space is available.</p><a class="btn btn-sm btn-neutral rounded-pill" href="/advertise">Advertise here</a></div>',
        ),
        AdSlot(
            key="in_article_1", name="In-article", placement="in_article",
            format="fluid", pricing_model=AdPricingModel.CPM, base_price_minor=1200,
            max_concurrent=1,
        ),
        AdSlot(
            key="feed_native", name="Between feed cards", placement="feed",
            format="fluid", pricing_model=AdPricingModel.CPC, base_price_minor=150,
        ),
        AdSlot(
            key="footer_banner", name="Footer banner", placement="footer",
            format="728x90", width=728, height=90,
            pricing_model=AdPricingModel.FLAT_WEEKLY, base_price_minor=15000,
        ),
    ])


CATEGORIES = [
    ("Engineering", "bi-cpu", "primary", "How things are built, and why they broke."),
    ("AI and data", "bi-diagram-3", "warning", "Models, pipelines and what they are actually good for."),
    ("Security", "bi-shield-lock", "danger", "Breaking things carefully, then fixing them."),
    ("Working", "bi-compass", "info", "Process, clients and the business of building software."),
]


async def seed_blog(db, owner: User) -> None:
    if await db.scalar(select(Post.id).limit(1)):
        return

    from app.services.text import slugify

    categories = {}
    for position, (name, icon, accent, description) in enumerate(CATEGORIES):
        category = Category(
            name=name, slug=slugify(name), icon=icon, accent=accent,
            description=description, position=position,
        )
        db.add(category)
        categories[name] = category
    await db.flush()

    blocks = [
        ContentBlockIn(
            type=BlockType.RICH_TEXT,
            data={"html": "<p>Every blog engine eventually hits the same wall: someone wants to embed a poll, or a podcast clip, or a table, and the schema says the body is a single text column.</p>"},
        ),
        ContentBlockIn(
            type=BlockType.HEADING, data={"text": "Blocks, not a body", "level": 2}
        ),
        ContentBlockIn(
            type=BlockType.MARKDOWN,
            data={"source": "A post here is an ordered list of rows. Each row has a `type` and a JSON `data` payload. Adding a format means writing a renderer on the client — the database never changes."},
        ),
        ContentBlockIn(
            type=BlockType.CODE,
            data={
                "language": "python",
                "filename": "models/post.py",
                "source": 'class ContentBlock(Base):\n    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))\n    type: Mapped[str] = mapped_column(String(30))\n    position: Mapped[int] = mapped_column(Integer, default=0)\n    data: Mapped[dict] = mapped_column(JSON, default=dict)',
                "show_line_numbers": True,
            },
        ),
        ContentBlockIn(
            type=BlockType.CALLOUT,
            data={"html": "<p>Rendering happens on write, not on read. A page view is a plain select.</p>", "tone": "info", "icon": "bi-lightbulb"},
        ),
    ]

    post = Post(
        title="Why this blog stores posts as blocks",
        slug="why-this-blog-stores-posts-as-blocks",
        subtitle="A schema that does not need a migration every time the content changes shape",
        category_id=categories["Engineering"].id,
        author_id=owner.id,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(timezone.utc) - timedelta(days=2),
        is_featured=True,
        excerpt="Twenty-one content formats, one table, and no migration when the twenty-second arrives.",
    )
    db.add(post)
    await db.flush()

    for position, payload in enumerate(blocks):
        db.add(
            ContentBlock(
                post_id=post.id, type=payload.type, position=position,
                data=normalise_block(payload), settings={},
                anchor=slugify(payload.data.get("text", ""))[:120] if payload.type == BlockType.HEADING else None,
            )
        )
    await db.flush()
    await db.refresh(post, ["blocks", "tags"])
    recompute_metrics(post)

    for name in ("architecture", "postgresql", "fastapi"):
        tag = Tag(name=name, slug=slugify(name), usage_count=1)
        db.add(tag)
        post.tags.append(tag)


async def initialise() -> None:
    """Create tables and seed on first run. Safe to call on every boot."""
    await create_schema()
    async with session_scope() as db:
        roles = await seed_roles(db)
        owner = await seed_owner(db, roles)
        await seed_portfolio(db)
        await seed_commerce(db)
        await seed_blog(db, owner)
    logger.info("Database ready.")
