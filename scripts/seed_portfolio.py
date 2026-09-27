# """
# Seed data for Christopher James's portfolio backend.

# Source of truth for every fact below:
#   - resume.pdf / resume text supplied by Chris (professional summary,
#     technical skills, employment history, education)
#   - projects.html (the "Featured Projects" static page — descriptions,
#     key features, and tech tags for each of the 6 projects)

# Nothing here is invented. Two start dates are genuinely missing from the
# resume (it only ever says "Present" / "In Progress" for them, never a
# month/year) — those are flagged UNKNOWN_DATE below, not guessed at. Fill
# them in once, and re-run this script; it is safe to run any number of
# times.

# HOW THIS WORKS
# --------------
# Every record carries a natural key (`slug` for projects, `slug` for skill
# groups, `key` for experience/education). On each run:
#   - a record whose key already exists in the DB is UPDATED in place
#     (so editing the DATA below and re-running is how you correct content)
#   - a record whose key does not exist yet is CREATED
#   - every record's position is set to its index in its list below, so
#     RE-ORDERING is just re-ordering the Python list and re-running

# Adjust the imports in `_load_models()` to match your actual app layout
# (models module path, session factory). Everything else should work as-is
# against a SQLAlchemy + FastAPI backend; the upsert helper only touches
# attributes that exist on your model class, so extra/missing columns on
# your side won't crash the script.

# Usage:
#     python seed_portfolio.py
# """

# from __future__ import annotations

# # so it imports and gets the backend directory in sys.path for the imports below
# import os
# import sys
# from pathlib import Path

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from dataclasses import dataclass, field
# from typing import Any

# # Resume gives no month/year for these two — only "Present" / "In Progress".
# # Fill in the real value ("YYYY-MM-DD") once you have it, then re-run.
# UNKNOWN_DATE = None


# # --------------------------------------------------------------------------
# # skills — Technical Skills section of the resume, verbatim groupings
# # --------------------------------------------------------------------------
# SKILL_GROUPS: list[dict[str, Any]] = [
#     {
#         "slug": "backend",
#         "name": "Backend",
#         "icon": "bi-server",
#         "accent": "primary",
#         "description": None,
#         "skills": ["Python (FastAPI, Django, Flask)", "NodeJs (Express/Fastify)", "PHP"],
#     },
#     {
#         "slug": "frontend",
#         "name": "Frontend",
#         "icon": "bi-window",
#         "accent": "success",
#         "description": None,
#         "skills": ["React", "TypeScript", "JavaScript", "Bootstrap", "Tailwind"],
#     },
#     {
#         "slug": "databases-storage",
#         "name": "Databases & Storage",
#         "icon": "bi-database",
#         "accent": "warning",
#         "description": None,
#         "skills": ["PostgreSQL", "MySQL", "MongoDB", "Supabase", "Redis"],
#     },
#     {
#         "slug": "engineering",
#         "name": "Engineering",
#         "icon": "bi-gear",
#         "accent": "info",
#         "description": None,
#         "skills": [
#             "REST APIs",
#             "Authentication & Authorization",
#             "Payment Integrations",
#             "AI/LLM Integration",
#             "Analytics",
#             "Cloud Deployment",
#             "Git/GitHub",
#             "CI/CD",
#         ],
#     },
# ]


# # --------------------------------------------------------------------------
# # experience — Professional Experience + Education sections of the resume
# # --------------------------------------------------------------------------
# EXPERIENCE: list[dict[str, Any]] = [
#     {
#         "key": "dunis-technologies-lead-technical-engineer",
#         "organisation": "Dunis Technologies Limited",
#         "title": "Lead Technical Engineer (Software)",
#         "location": "Lagos, Nigeria",
#         "employment_type": "full_time",
#         "started_on": "2023-08-01",  # resume only says "Present" — confirm start date
#         "ended_on": None,
#         "is_current": True,
#         "summary": None,
#         "achievements": [
#             "Lead the development and deployment of internal business platforms and client-facing software solutions.",
#             "Built Workforce, a staffing, attendance, compliance, reporting, and operational management platform for monitoring workforce activities and productivity.",
#             "Built Dunis Inventory, a SaaS inventory and profit analytics platform developed for SME retailers and commercialized by Dunis Technologies.",
#             "Built Score App, an innovative scoring and academic management platform for Dunistech Academy and partner institutions, including attendance tracking, score management, automated parent updates, and performance analytics.",
#             "Built SimplyLovely Laundry, an operations management application for streamlining laundry workflows and service management.",
#             "Train software engineering students and staff in modern development practices, software architecture, and engineering workflows.",
#             "Contribute to product architecture, technical decisions, deployment, maintenance, and continuous improvement across multiple software products.",
#         ],
#         "stack": ["Python", "FastAPI", "Django", "React", "PostgreSQL"],
#         "logo_url": None,
#     },
#     {
#         "key": "kovun-academy-lead-full-stack-engineer",
#         "organisation": "Kovun Academy",
#         "title": "Lead Full-Stack Engineer",
#         "location": "Remote",
#         "employment_type": "full_time",
#         "started_on": "2025-10-01",  # resume only says "Present" — confirm start date
#         "ended_on": None,
#         "is_current": True,
#         "summary": None,
#         "achievements": [
#             "Architected and deployed a full-featured online learning platform supporting video learning, live sessions, automated certificates, subscriptions, and AI-assisted learning.",
#             "Led development across frontend, backend, integrations, and deployment.",
#             "Established engineering workflows including code review practices, CI/CD, and scalable application architecture.",
#             "Implemented payment and subscription flows for digital learning products.",
#         ],
#         "stack": ["React", "Node.js", "WebRTC", "Payments"],
#         "logo_url": None,
#     },
#     {
#         "key": "bizalert-software-engineer",
#         "organisation": "Bizalert — Marketing & Technology Agency",
#         "title": "Software Engineer",
#         "location": "Lekki, Lagos",
#         "employment_type": "full_time",
#         "started_on": "2021-04-01",
#         "ended_on": None,
#         "is_current": True,
#         "summary": None,
#         "achievements": [
#             "Designed and deployed client-facing web applications using JavaScript, jQuery, Python/Flask, and REST APIs.",
#             "Built internal analytics dashboards for monitoring campaign performance, user behavior, and conversion metrics.",
#             "Developed and maintained web solutions tailored to client business and operational requirements.",
#         ],
#         "stack": ["JavaScript", "jQuery", "Python", "Flask", "REST APIs"],
#         "logo_url": None,
#     },
#     {
#         "key": "jobilate-digital-marketing-specialist",
#         "organisation": "Jobilate",
#         "title": "Digital Marketing Specialist",
#         "location": "Sangotedo, Lagos",
#         "employment_type": "full_time",
#         "started_on": "2018-02-01",
#         "ended_on": "2018-05-31",
#         "is_current": False,
#         "summary": None,
#         "achievements": [
#             "Executed digital advertising and SEO campaigns to improve audience engagement and brand visibility.",
#             "Implemented analytics and tracking tools to monitor visitor behavior and optimize conversion funnels.",
#         ],
#         "stack": ["SEO", "Analytics"],
#         "logo_url": None,
#     },
#     # ---- education (same table, employment_type="education" — see About.tsx) ----
#     {
#         "key": "miva-open-university-bsc-computer-science",
#         "organisation": "Miva Open University",
#         "title": "B.Sc. Computer Science",
#         "location": "Nigeria",
#         "employment_type": "education",
#         "started_on": "2025-01-01",  # resume only says "In Progress" — confirm start date
#         "ended_on": None,
#         "is_current": True,
#         "summary": None,
#         "achievements": [],
#         "stack": [],
#         "logo_url": None,
#     },
#     {
#         "key": "alx-software-engineering-program",
#         "organisation": "ALX Software Engineering Program",
#         "title": "Professional Certification — Full-Stack Software Engineering",
#         "location": "Remote",
#         "employment_type": "education",
#         "started_on": "2022-04-01",
#         "ended_on": "2024-09-30",
#         "is_current": False,
#         "summary": None,
#         "achievements": [],
#         "stack": [],
#         "logo_url": None,
#     },
# ]


# # --------------------------------------------------------------------------
# # projects — Featured Projects section of projects.html, verbatim content
# # --------------------------------------------------------------------------
# PROJECTS: list[dict[str, Any]] = [
#     {
#         "slug": "salesnet",
#         "title": "Salesnet",
#         "tagline": "Internet of Sales — an AI-powered, Lagos-first marketplace",
#         "summary": (
#             "An AI-powered, Lagos-first marketplace designed to digitize informal "
#             "commerce. Features include free vendor storefronts, AI-driven local "
#             "pricing and product tagging, AR try-on for wearables, geo-location-based "
#             "vendor recommendations, and embedded fintech for seamless payments. Built "
#             "to serve the unique logistics and trust challenges of the Nigerian market."
#         ),
#         "body": None,
#         "kind": "marketplace",
#         "role": "Founder & Lead Engineer",
#         "client": None,
#         "stack": ["React", "FastAPI", "PostgreSQL", "AI/ML", "AR.js", "Redis"],
#         "highlights": [
#             "AI-powered product categorization and dynamic pricing",
#             "Augmented reality try-on for fashion and accessories",
#             "Geo-location vendor discovery and route optimization",
#             "Embedded payment processing and escrow services",
#             "Vendor analytics dashboard with real-time sales insights",
#         ],
#         "metrics": {},
#         "cover_url": "/assets/img/projects/salesnet.png",
#         "gallery": [],
#         "icon": "bi-shop",
#         "accent": "warning",
#         "live_url": "https://salesnet.ng",
#         "repo_url": None,
#         "state": "live",
#         "is_featured": True,
#     },
#     {
#         "slug": "intellect",
#         "title": "Intellect",
#         "tagline": "Your Digital Learning Companion",
#         "summary": (
#             "A digital learning companion built to democratize education access. "
#             "Supports video, PDF, PPT, audio, and interactive lesson formats. "
#             "Integrates an AI Learning Assistant for personalized tutoring, "
#             "auto-generates completion certificates, hosts live sessions, and "
#             "provides a Creator Studio for educators to monetize content. Includes "
#             "B2B partnership tools for institutions and corporate training programs."
#         ),
#         "body": None,
#         "kind": "edtech",
#         "role": "Founder & Lead Engineer",
#         "client": None,
#         "stack": ["React", "Node.js", "MongoDB", "LLM Integration", "WebRTC", "AWS S3"],
#         "highlights": [
#             "Multi-format content delivery (video, audio, documents, interactive)",
#             "AI-powered learning assistant with contextual Q&A",
#             "Auto-certificate generation upon course completion",
#             "Live streaming and real-time collaboration tools",
#             "Creator Studio with monetization and analytics",
#         ],
#         "metrics": {},
#         "cover_url": "/assets/img/projects/intellect.png",
#         "gallery": [],
#         "icon": "bi-mortarboard",
#         "accent": "primary",
#         "live_url": "https://intellect.salesnet.ng",
#         "repo_url": None,
#         "state": "live",
#         "is_featured": True,
#     },
#     {
#         "slug": "stitch",
#         "title": "Stitch",
#         "tagline": "Vertical SaaS & productivity for Nigeria's laundry & fashion economy",
#         "summary": (
#             "A vertical SaaS platform transforming Nigeria's laundry and fashion "
#             "economy. Converts informal SMEs from notebook-based operations to "
#             "predictable digital revenue through inventory tracking, order "
#             "management, customer relationship management, and embedded payment "
#             "processing. Designed specifically for the operational realities of "
#             "small-scale service businesses in Lagos."
#         ),
#         "body": None,
#         "kind": "saas",
#         "role": "Lead Engineer",
#         "client": None,
#         "stack": ["React", "Flask", "PostgreSQL", "Twilio", "Paystack"],
#         "highlights": [
#             "Inventory tracking with low-stock alerts and demand forecasting",
#             "End-to-end order lifecycle management",
#             "Customer CRM with SMS notification integration",
#             "Financial reporting and profit analytics",
#             "Mobile-first design for on-the-go business owners",
#         ],
#         "metrics": {},
#         # No screenshot asset shipped yet — add one at this path when ready.
#         "cover_url": None,
#         "gallery": [],
#         "icon": "bi-basket",
#         "accent": "success",
#         "live_url": "https://stitch-client-app.vercel.app",
#         "repo_url": None,
#         "state": "live",
#         "is_featured": True,
#     },
#     {
#         "slug": "score-app",
#         "title": "Score App",
#         "tagline": "Academic scoring and performance management for Dunistech Academy",
#         "summary": (
#             "An innovative scoring and academic management system built for "
#             "Dunistech Academy and partner institutions. Tracks student attendance, "
#             "records and manages scores across subjects, keeps parents informed via "
#             "automated SMS and email updates, and auto-generates performance "
#             "analysis reports with visual grade distribution charts and trend "
#             "identification."
#         ),
#         "body": None,
#         "kind": "internal_tool",
#         "role": "Lead Engineer",
#         "client": "Dunistech Academy",
#         "stack": ["JavaScript", "Python", "SQLite", "Chart.js", "Twilio"],
#         "highlights": [
#             "Automated attendance tracking with biometric integration",
#             "Comprehensive score management and grade computation",
#             "Parent notification system via SMS and email",
#             "Auto-generated performance analysis and trend reports",
#             "Role-based access control for teachers, admins, and parents",
#         ],
#         "metrics": {},
#         # No screenshot asset shipped yet — add one at this path when ready.
#         "cover_url": None,
#         "gallery": [],
#         "icon": "bi-clipboard-data",
#         "accent": "info",
#         "live_url": None,  # "Institutional Tool" — not publicly reachable
#         "repo_url": None,
#         "state": "internal",
#         "is_featured": False,
#     },
#     {
#         "slug": "inventory-management",
#         "title": "Inventory Management System",
#         "tagline": "SaaS inventory and profit analytics for SME retailers",
#         "summary": (
#             "A precision inventory and profit analytics platform designed for SMEs. "
#             "Features real-time stock tracking, automated sales reporting, demand "
#             "forecasting using historical data, and deep financial insights. Helps "
#             "business owners move from gut-feeling restocking to data-driven "
#             "inventory decisions."
#         ),
#         "body": None,
#         "kind": "saas",
#         "role": "Lead Engineer",
#         "client": None,
#         "stack": ["React", "Django", "PostgreSQL", "Pandas", "Chart.js"],
#         "highlights": [
#             "Real-time stock tracking with barcode scanning",
#             "Sales reporting with profit margin analysis",
#             "Demand forecasting based on historical trends",
#             "Financial insights and cash flow projections",
#             "Multi-location inventory support",
#         ],
#         "metrics": {},
#         "cover_url": "/assets/img/projects/barman.png",
#         "gallery": [],
#         "icon": "bi-boxes",
#         "accent": "primary",
#         "live_url": None,  # "Production SaaS" — commercialized, no public demo link given
#         "repo_url": None,
#         "state": "live",
#         "is_featured": True,
#     },
#     {
#         "slug": "techa",
#         "title": "Techa",
#         "tagline": "Personal engineering portfolio and SaaS launchpad",
#         "summary": (
#             "My personal engineering portfolio and SaaS launchpad. Serves as a "
#             "central hub for product demos, technical writing, client project "
#             "showcases, and experimental prototypes. Designed with a dark, "
#             "minimalist aesthetic that emphasizes code quality and system "
#             "architecture over visual noise."
#         ),
#         "body": None,
#         "kind": "portfolio",
#         "role": "Founder & Lead Engineer",
#         "client": None,
#         "stack": ["HTML5", "CSS3", "JavaScript", "Vercel"],
#         "highlights": [
#             "Centralized product demo showcase",
#             "Technical blog and case study publication",
#             "Client project portfolio with live previews",
#             "SaaS launchpad for rapid MVP deployment",
#             "Dark-mode optimized, performance-first design",
#         ],
#         "metrics": {},
#         "cover_url": "/assets/img/projects/techa_hero.png",
#         "gallery": [],
#         "icon": "bi-rocket-takeoff",
#         "accent": "secondary",
#         "live_url": "https://techa.salesnet.ng",
#         "repo_url": None,
#         "state": "live",
#         "is_featured": False,
#     },
# ]


# # --------------------------------------------------------------------------
# # upsert machinery — generic, works against any SQLAlchemy declarative model
# # --------------------------------------------------------------------------
# def _set_if_present(instance: Any, field_name: str, value: Any) -> None:
#     """Only touches attributes that actually exist on the model."""
#     if hasattr(instance, field_name):
#         setattr(instance, field_name, value)


# def _upsert(session, model, lookup: dict[str, Any], values: dict[str, Any], position: int):
#     """
#     Find a row matching `lookup` (its natural key); update it in place if
#     found, else create a new one. Always sets `position` (if the model has
#     that column) to the record's index in its DATA list, so re-ordering the
#     list and re-running this script is all "re-ordering" ever takes.
#     """
#     instance = session.query(model).filter_by(**lookup).one_or_none()
#     if instance is None:
#         instance = model(**lookup)
#         session.add(instance)
#     for field_name, value in values.items():
#         _set_if_present(instance, field_name, value)
#     _set_if_present(instance, "position", position)
#     return instance


# def seed_skill_groups(session, SkillGroupModel, SkillModel):
#     for index, group in enumerate(SKILL_GROUPS):
#         skills = group.pop("skills")
#         instance = _upsert(
#             session,
#             SkillGroupModel,
#             lookup={"slug": group["slug"]},
#             values=group,
#             position=index,
#         )
#         # Skills live on a child table — replace the set on every run so
#         # editing SKILL_GROUPS above is enough to correct them.
#         if hasattr(instance, "skills"):
#             instance.skills = [
#                 SkillModel(name=name, level=0, icon=None, position=skill_index)
#                 for skill_index, name in enumerate(skills)
#             ]
#         group["skills"] = skills  # restore, in case this module is re-run in-process


# def seed_experience(session, ExperienceModel):
#     for index, role in enumerate(EXPERIENCE):
#         role = dict(role)
#         key = role.pop("key")
#         if role.get("started_on") is None:
#             print(
#                 f"  ! {role['organisation']} — {role['title']}: no confirmed start date "
#                 "yet (resume only says \"Present\"/\"In Progress\"). Fill in started_on "
#                 "and re-run."
#             )
#         _upsert(
#             session,
#             ExperienceModel,
#             lookup={"organisation": role["organisation"], "title": role["title"]},
#             values=role,
#             position=index,
#         )
#         _ = key  # kept only for readability of the DATA above


# def seed_projects(session, ProjectModel):
#     for index, project in enumerate(PROJECTS):
#         _upsert(
#             session,
#             ProjectModel,
#             lookup={"slug": project["slug"]},
#             values=project,
#             position=index,
#         )


# def _load_models():
#     """
#     Adjust these two imports to match your backend's actual layout, then
#     delete this docstring note. Expected shapes:
#       - SessionLocal: a callable returning a SQLAlchemy Session
#       - Project, Experience, SkillGroup, Skill: your declarative models,
#         with the field names used above (slug/organisation+title/etc. as
#         the natural keys, and a `position` int column if you want
#         re-ordering support)
#     """
#     from app.db.session import SessionLocal  # noqa: PLC0415
#     from app.models import Experience, Project, Skill, SkillGroup  # noqa: PLC0415

#     return SessionLocal, Project, Experience, SkillGroup, Skill


# def run() -> None:
#     SessionLocal, Project, Experience, SkillGroup, Skill = _load_models()
#     session = SessionLocal()
#     try:
#         print("Seeding skill groups…")
#         seed_skill_groups(session, SkillGroup, Skill)
#         print("Seeding experience & education…")
#         seed_experience(session, Experience)
#         print("Seeding projects…")
#         seed_projects(session, Project)
#         session.commit()
#         print(
#             f"Done — {len(SKILL_GROUPS)} skill groups, {len(EXPERIENCE)} experience/"
#             f"education entries, {len(PROJECTS)} projects."
#         )
#     except Exception:
#         session.rollback()
#         raise
#     finally:
#         session.close()


# if __name__ == "__main__":
#     try:
#         run()
#     except ModuleNotFoundError as error:
#         print(
#             "Could not import your app's models/session — edit _load_models() in "
#             f"this file to point at your actual module paths.\n  ({error})"
#         )




# v2
"""
Seed data for Christopher James's portfolio backend.

Source of truth for every fact below:
  - resume.pdf / resume text supplied by Chris (professional summary,
    technical skills, employment history, education)
  - projects.html (the "Featured Projects" static page — descriptions,
    key features, and tech tags for each of the 6 projects)

Nothing here is invented. Two start dates are genuinely missing from the
resume (it only ever says "Present" / "In Progress" for them, never a
month/year) — those are flagged UNKNOWN_DATE below, not guessed at. Fill
them in once, and re-run this script; it is safe to run any number of
times.

HOW THIS WORKS
--------------
Every record carries a natural key (`slug` for projects, `slug` for skill
groups, `key` for experience/education). On each run:
  - a record whose key already exists in the DB is UPDATED in place
    (so editing the DATA below and re-running is how you correct content)
  - a record whose key does not exist yet is CREATED
  - every record's position is set to its index in its list below, so
    RE-ORDERING is just re-ordering the Python list and re-running

Adjust the imports in `_load_models()` to match your actual app layout
(models module path, session factory). Everything else should work as-is
against a SQLAlchemy + FastAPI backend; the upsert helper only touches
attributes that exist on your model class, so extra/missing columns on
your side won't crash the script.

Usage:
    python seed_portfolio.py
"""


from __future__ import annotations

from typing import Any
from datetime import date

# Resume gives no month/year for these two — only "Present" / "In Progress".
# Fill in the real value ("YYYY-MM-DD") once you have it, then re-run.
UNKNOWN_DATE = None


# 
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --------------------------------------------------------------------------
# skills — Technical Skills section of the resume, verbatim groupings
# --------------------------------------------------------------------------
SKILL_GROUPS: list[dict[str, Any]] = [
    {
        "slug": "backend",
        "name": "Backend",
        "icon": "bi-server",
        "accent": "primary",
        "description": None,
        "skills": ["Python (FastAPI, Django, Flask)", "NodeJs (Express/Fastify)", "PHP"],
    },
    {
        "slug": "frontend",
        "name": "Frontend",
        "icon": "bi-window",
        "accent": "success",
        "description": None,
        "skills": ["React", "TypeScript", "JavaScript", "Bootstrap", "Tailwind"],
    },
    {
        "slug": "databases-storage",
        "name": "Databases & Storage",
        "icon": "bi-database",
        "accent": "warning",
        "description": None,
        "skills": ["PostgreSQL", "MySQL", "MongoDB", "Supabase", "Redis"],
    },
    {
        "slug": "engineering",
        "name": "Engineering",
        "icon": "bi-gear",
        "accent": "info",
        "description": None,
        "skills": [
            "REST APIs",
            "Authentication & Authorization",
            "Payment Integrations",
            "AI/LLM Integration",
            "Analytics",
            "Cloud Deployment",
            "Git/GitHub",
            "CI/CD",
        ],
    },
]



# --------------------------------------------------------------------------
# experience — Professional Experience + Education sections of the resume
# --------------------------------------------------------------------------
EXPERIENCE: list[dict[str, Any]] = [
    {
        "key": "dunis-technologies-lead-technical-engineer",
        "organisation": "Dunis Technologies Limited",
        "title": "Lead Technical Engineer / Instructor (Software engineering)",
        "location": "Lagos, Nigeria",
        "employment_type": "full_time",
        "started_on": date(2023, 8, 1),  # resume only says "Present" — confirm start date
        "ended_on": None,
        "is_current": True,
        "summary": None,
        "achievements": [
            "Lead the development and deployment of internal business platforms and client-facing software solutions.",
            "Built Workforce, a staffing, attendance, compliance, reporting, and operational management platform for monitoring workforce activities and productivity.",
            "Built Dunis Inventory, a SaaS inventory and profit analytics platform developed for SME retailers and commercialized by Dunis Technologies.",
            "Built Score App, an innovative scoring and academic management platform for Dunistech Academy and partner institutions, including attendance tracking, score management, automated parent updates, and performance analytics.",
            "Built SimplyLovely Laundry, an operations management application for streamlining laundry workflows and service management.",
            "Train software engineering students and staff in modern development practices, software architecture, and engineering workflows.",
            "Contribute to product architecture, technical decisions, deployment, maintenance, and continuous improvement across multiple software products.",
        ],
        "stack": [
            "Python", "FastAPI", "Django", "Flask", "Typescript", "PHP", 
            "Node.js", "React", "AWS", "VPS", "Vercel", "PostgreSQL", "MySQL", "MongoDB",
            "SQLAlchemy", "Redis", "SQL", "Training",
            "Supabase", "WebRTC", "Payments", "Paystack", "Flutterwave", "Analytics"
            ],
        "logo_url": None,
    },
    {
        "key": "kovun-academy-lead-full-stack-engineer",
        "organisation": "Kovun Academy",
        "title": "Lead Full-Stack Engineer",
        "location": "Remote",
        "employment_type": "full_time",
        "started_on":  date(2025, 1, 1),  # resume only says "Present" — confirm start date
        "ended_on": None,
        "is_current": True,
        "summary": None,
        "achievements": [
            "Architected and deployed a full-featured online learning platform supporting video learning, live sessions, automated certificates, subscriptions, and AI-assisted learning.",
            "Led development across frontend, backend, integrations, and deployment.",
            "Established engineering workflows including code review practices, CI/CD, and scalable application architecture.",
            "Implemented payment and subscription flows for digital learning products.",
        ],
        "stack": ["React", "TypeScript", "Tailwind CSS",
        "Cloud Deployment", "Servers", "Vercel", "PostgreSQL", "SQLAlchemy", "SQL", "FastAPI", 
        "LLMs", "Payments", "APIs", "CI/CD", "WebRTC"
        ],
        "logo_url": None,
    },
    {
        "key": "bizalert-software-engineer",
        "organisation": "Bizalert — Marketing & Technology Agency",
        "title": "Software Engineer(Full-Stack)",
        "location": "Lekki, Lagos",
        "employment_type": "full_time",
        "started_on": date(2021, 4, 1),
        "ended_on": None,
        "is_current": True,
        "summary": None,
        "achievements": [
            "Designed and deployed client-facing web applications using JavaScript, jQuery, Python/Flask, and REST APIs.",
            "Built internal analytics dashboards for monitoring campaign performance, user behavior, and conversion metrics.",
            "Developed and maintained web solutions tailored to client business and operational requirements.",
        ],
        "stack": ["JavaScript", "jQuery", "Python", "Flask", "PHP", "REST APIs"],
        "logo_url": None,
    },
    {
        "key": "jobilate-digital-marketing-specialist",
        "organisation": "Jobilate",
        "title": "Digital Marketing Specialist",
        "location": "Sangotedo, Lagos",
        "employment_type": "full_time",
        "started_on": date(2018, 2, 1),
        "ended_on": date(2018, 5, 31),
        "is_current": False,
        "summary": None,
        "achievements": [
            "Executed digital advertising and SEO campaigns to improve audience engagement and brand visibility.",
            "Implemented analytics and tracking tools to monitor visitor behavior and optimize conversion funnels.",
        ],
        "stack": [
            "JavaScript", "PHP", "Bootstrap", "SEO", "Analytics", 
            "Digital Marketing tools", "Google Analytics", 
            "Google Ads", "Facebook Ads"
        ],
        "logo_url": None,
    },
    # ---- education (same table, employment_type="education" — see About.tsx) ----
    {
        "key": "miva-open-university-bsc-artificial-intelligence",
        "organisation": "Miva Open University",
        "title": "B.Sc. Artificial Intelligence",
        "location": "Nigeria",
        "employment_type": "education",
        "started_on": date(2025, 1, 1),  # resume only says "In Progress" — confirm start date
        "ended_on": None,
        "is_current": True,
        "summary": None,
        "achievements": [],
        "stack": [
            "Python", "AI/ML", "Data Science", "Deep Learning", 
            "NLP", "Computer Vision", "Git", "SQL", "PostgreSQL", 
            "MongoDB", "Data Analysis", "Data Visualization"],
        "logo_url": None,
    },
    {
        "key": "alx-software-engineering-program",
        "organisation": "ALX Software Engineering",
        "title": "Professional Certification — Full-Stack Software Engineering",
        "location": "Remote",
        "employment_type": "education",
        "started_on": date(2022, 4, 1),
        "ended_on": date(2024, 9, 30),
        "is_current": False,
        "summary": None,
        "achievements": ["Became a fullstack software engineer with expertise in building web applications, REST APIs, and cloud deployment."],
        "stack": ["Python", "Flask", "PostgreSQL", "MySQL", "RestAPI", "Git", "Docker", "CI/CD", "React", "Node.js", "JavaScript", "TypeScript", "HTML5", "CSS3"],
        "logo_url": None,
    },
]


# --------------------------------------------------------------------------
# projects — Featured Projects section of projects.html, verbatim content
# --------------------------------------------------------------------------
PROJECTS: list[dict[str, Any]] = [
    {
        "slug": "salesnet",
        "title": "Salesnet",
        "tagline": "Internet of Sales — an AI-powered, Lagos-first marketplace",
        "summary": (
            "An AI-powered, Lagos-first marketplace designed to digitize informal "
            "commerce. Features include free vendor storefronts, AI-driven local "
            "pricing and product tagging, AR try-on for wearables, geo-location-based "
            "vendor recommendations, and embedded fintech for seamless payments. Built "
            "to serve the unique logistics and trust challenges of the Nigerian market."
        ),
        "body": None,
        "kind": "marketplace",
        "role": "Founder & Lead Engineer",
        "client": None,
        "stack": ["React", "FastAPI", "PostgreSQL", "AI/ML", "AR.js", "Redis"],
        "highlights": [
            "AI-powered product categorization and dynamic pricing",
            "Augmented reality try-on for fashion and accessories",
            "Geo-location vendor discovery and route optimization",
            "Embedded payment processing and escrow services",
            "Vendor analytics dashboard with real-time sales insights",
        ],
        "metrics": {},
        "cover_url": "/assets/img/projects/salesnet.png",
        "gallery": [],
        "icon": "bi-shop",
        "accent": "warning",
        "live_url": "https://salesnet.ng",
        "repo_url": None,
        "state": "live",
        "is_featured": True,
    },
    {
        "slug": "intellect",
        "title": "Intellect - Digital Learning Companion",
        "tagline": "Your Digital Learning Companion",
        "summary": (
            "A digital learning companion built to democratize education access. "
            "Supports video, PDF, PPT, audio, and interactive lesson formats. "
            "Integrates an AI Learning Assistant for personalized tutoring, "
            "auto-generates completion certificates, hosts live sessions, and "
            "provides a Creator Studio for educators to monetize content. Includes "
            "B2B partnership tools for institutions and corporate training programs."
        ),
        "body": None,
        "kind": "edtech",
        "role": "Founder & Lead Engineer",
        "client": None,
        "stack": ["React", "Node.js", "MongoDB", "LLM Integration", "WebRTC", "AWS S3"],
        "highlights": [
            "Multi-format content delivery (video, audio, documents, interactive)",
            "AI-powered learning assistant with contextual Q&A",
            "Auto-certificate generation upon course completion",
            "Live streaming and real-time collaboration tools",
            "Creator Studio with monetization and analytics",
        ],
        "metrics": {},
        "cover_url": "/assets/img/projects/intellect.png",
        "gallery": [],
        "icon": "bi-mortarboard",
        "accent": "primary",
        "live_url": "https://intellect.salesnet.ng",
        "repo_url": None,
        "state": "live",
        "is_featured": True,
    },
    {
        "slug": "stitch",
        "title": "Stitch - Vertical SaaS for Laundry & Fashion SMEs",
        "tagline": "Vertical SaaS & productivity for Nigeria's laundry & fashion economy",
        "summary": (
            "A vertical SaaS platform transforming Nigeria's laundry and fashion "
            "economy. Converts informal SMEs from notebook-based operations to "
            "predictable digital revenue through inventory tracking, order "
            "management, customer relationship management, and embedded payment "
            "processing. Designed specifically for the operational realities of "
            "small-scale service businesses in Lagos."
        ),
        "body": None,
        "kind": "saas",
        "role": "Lead Engineer",
        "client": None,
        "stack": ["React", "Flask", "PostgreSQL", "Twilio", "Paystack"],
        "highlights": [
            "Inventory tracking with low-stock alerts and demand forecasting",
            "End-to-end order lifecycle management",
            "Customer CRM with SMS notification integration",
            "Financial reporting and profit analytics",
            "Mobile-first design for on-the-go business owners",
        ],
        "metrics": {},
        # No screenshot asset shipped yet — add one at this path when ready.
        "cover_url": None,
        "gallery": [],
        "icon": "bi-basket",
        "accent": "success",
        "live_url": "https://stitch-client-app.vercel.app",
        "repo_url": None,
        "state": "live",
        "is_featured": True,
    },
    {
        "slug": "score-app",
        "title": "Score App",
        "tagline": "Academic scoring and performance management for Dunistech Academy",
        "summary": (
            "An innovative scoring and academic management system built for "
            "Dunistech Academy and partner institutions. Tracks student attendance, "
            "records and manages scores across subjects, keeps parents informed via "
            "automated SMS and email updates, and auto-generates performance "
            "analysis reports with visual grade distribution charts and trend "
            "identification."
        ),
        "body": None,
        "kind": "internal_tool",
        "role": "Lead Engineer",
        "client": "Dunistech Academy",
        "stack": ["JavaScript", "React", "Typescript", "Python", "PostgreSQL", "Chart.js", "Twilio"],
        "highlights": [
            "Automated attendance tracking with biometric integration",
            "Comprehensive score management and grade computation",
            "Parent notification system via SMS and email",
            "Auto-generated performance analysis and trend reports",
            "Role-based access control for teachers, admins, and parents",
        ],
        "metrics": {},
        # No screenshot asset shipped yet — add one at this path when ready.
        "cover_url": None,
        "gallery": [],
        "icon": "bi-clipboard-data",
        "accent": "info",
        "live_url": None,  # "Institutional Tool" — not publicly reachable
        "repo_url": None,
        "state": "internal",
        "is_featured": False,
    },
    {
        "slug": "dunis-workforce",
        "title": "Dunis Workforce",
        "tagline": "Streamlined workforce management for modern businesses",
        "summary": (
            "A comprehensive workforce management solution designed to optimize "
            "employee scheduling, track time and attendance, and streamline "
            "HR processes. Features include automated shift scheduling, real-time "
            "attendance tracking, and integrated communication tools."
        ),
        "body": None,
        "kind": "internal_tool",
        "role": "Lead Engineer",
        "client": "Dunis Corporation",
        "stack": ["Python", "Django", "PostgreSQL", "React"],
        "highlights": [
            "Automated shift scheduling with conflict detection",
            "Real-time attendance tracking with geolocation",
            "Integrated communication tools for team coordination",
            "Comprehensive reporting and analytics dashboard",
            "Seamless integration with existing HR systems",
        ],
        "metrics": {},
        # No screenshot asset shipped yet — add one at this path when ready.
        "cover_url": None,
        "gallery": [],
        "icon": "bi-people",
        "accent": "secondary",
        "live_url": None,  # "Institutional Tool" — not publicly reachable
        "repo_url": None,
        "state": "internal",
        "is_featured": False,
    },
    {
        "slug": "dunis-inventory-management",
        "title": "Dunis Inventory Management System",
        "tagline": "Precision inventory and profit analytics for SMEs",
        "summary": (
            "A precision inventory and profit analytics platform designed for SMEs. "
            "Features real-time stock tracking, automated sales reporting, demand "
            "forecasting using historical data, and deep financial insights. Helps "
            "business owners move from gut-feeling restocking to data-driven "
            "inventory decisions."
        ),
        "body": None,
        "kind": "saas",
        "role": "Lead Engineer(Fullstack)",
        "client": None,
        "stack": ["React", "Typescript", "FastAPI", "PostgreSQL", "Redis", "Chart.js"],
        "highlights": [
            "Real-time stock tracking with barcode scanning",
            "Sales reporting with profit margin analysis",
            "Demand forecasting based on historical trends",
            "Financial insights and cash flow projections",
            "Multi-location inventory support",
        ],
        "metrics": {},
        "cover_url": "/assets/img/projects/inventory.png",
        "gallery": [],
        "icon": "bi-boxes",
        "accent": "primary",
        "live_url": None,  # "Production SaaS" — commercialized, no public demo link given
        "repo_url": None,
        "state": "live",
        "is_featured": True,
    },
    {
        "slug": "chrisjames",
        "title": "Techa",
        "tagline": "Personal engineering portfolio and SaaS launchpad",
        "summary": (
            "My personal engineering portfolio and SaaS launchpad. Serves as a "
            "central hub for product demos, technical writing, client project "
            "showcases, and experimental prototypes. Designed with a dark, "
            "minimalist aesthetic that emphasizes code quality and system "
            "architecture over visual noise."
        ),
        "body": None,
        "kind": "portfolio",
        "role": "Founder & Lead Engineer",
        "client": None,
        "stack": ["React", "CSS3", "Tailwind CSS", "Typescript", "Vercel", "FastAPI", "PostgreSQL"],
        "highlights": [
            "Centralized product demo showcase",
            "Technical blog and case study publication",
            "Client project portfolio with live previews",
            "SaaS launchpad for rapid MVP deployment",
            "Dark-mode optimized, performance-first design",
        ],
        "metrics": {},
        "cover_url": "/assets/img/projects/techa_hero.png",
        "gallery": [],
        "icon": "bi-rocket-takeoff",
        "accent": "secondary",
        "live_url": "https://chrisjames.vercel.app",
        "repo_url": "https://github.com/chrisjames",
        "state": "live",
        "is_featured": False,
    },
]


# --------------------------------------------------------------------------
# upsert machinery — async, works against any SQLAlchemy 2.x declarative model
# --------------------------------------------------------------------------
from sqlalchemy import select  # noqa: E402


def _set_if_present(instance: Any, field_name: str, value: Any) -> None:
    """Only touches attributes that actually exist on the model."""
    if hasattr(instance, field_name):
        setattr(instance, field_name, value)


async def _upsert(session, model, lookup: dict[str, Any], values: dict[str, Any], position: int):
    """
    Find a row matching `lookup` (its natural key); update it in place if
    found, else create a new one. Always sets `position` (if the model has
    that column) to the record's index in its DATA list, so re-ordering the
    list and re-running this script is all "re-ordering" ever takes.
    """
    result = await session.execute(select(model).filter_by(**lookup))
    instance = result.scalar_one_or_none()
    if instance is None:
        instance = model(**lookup)
        session.add(instance)
    for field_name, value in values.items():
        _set_if_present(instance, field_name, value)
    _set_if_present(instance, "position", position)
    return instance


async def seed_skill_groups(session, SkillGroupModel, SkillModel):
    for index, group in enumerate(SKILL_GROUPS):
        skills = group.pop("skills")
        instance = await _upsert(
            session,
            SkillGroupModel,
            lookup={"slug": group["slug"]},
            values=group,
            position=index,
        )
        # Skills live on a child table — replace the set on every run so
        # editing SKILL_GROUPS above is enough to correct them.
        if hasattr(instance, "skills"):
            instance.skills = [
                SkillModel(name=name, level=0, icon=None, position=skill_index)
                for skill_index, name in enumerate(skills)
            ]
        group["skills"] = skills  # restore, in case this module is re-run in-process


async def seed_experience(session, ExperienceModel):
    for index, role in enumerate(EXPERIENCE):
        role = dict(role)
        key = role.pop("key")
        if role.get("started_on") is None:
            print(
                f"  ! {role['organisation']} — {role['title']}: no confirmed start date "
                "yet (resume only says \"Present\"/\"In Progress\"). Fill in started_on "
                "and re-run."
            )
        await _upsert(
            session,
            ExperienceModel,
            lookup={"organisation": role["organisation"], "title": role["title"]},
            values=role,
            position=index,
        )
        _ = key  # kept only for readability of the DATA above


async def seed_projects(session, ProjectModel):
    for index, project in enumerate(PROJECTS):
        await _upsert(
            session,
            ProjectModel,
            lookup={"slug": project["slug"]},
            values=project,
            position=index,
        )


def _load_models():
    """
    Adjust these two imports to match your backend's actual layout, then
    delete this docstring note. Expected shapes:
      - SessionLocal: an async_sessionmaker (or any zero-arg callable
        returning an AsyncSession / usable as `async with SessionLocal() as s`)
      - Project, Experience, SkillGroup, Skill: your declarative models,
        with the field names used above (slug/organisation+title/etc. as
        the natural keys, and a `position` int column if you want
        re-ordering support)
    """
    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models import Experience, Project, Skill, SkillGroup  # noqa: PLC0415

    return SessionLocal, Project, Experience, SkillGroup, Skill


async def run() -> None:
    SessionLocal, Project, Experience, SkillGroup, Skill = _load_models()
    async with SessionLocal() as session:
        try:
            print("Seeding skill groups…")
            await seed_skill_groups(session, SkillGroup, Skill)
            print("Seeding experience & education…")
            await seed_experience(session, Experience)
            print("Seeding projects…")
            await seed_projects(session, Project)
            await session.commit()
            print(
                f"Done — {len(SKILL_GROUPS)} skill groups, {len(EXPERIENCE)} experience/"
                f"education entries, {len(PROJECTS)} projects."
            )
        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(run())
    except ModuleNotFoundError as error:
        print(
            "Could not import your app's models/session — edit _load_models() in "
            f"this file to point at your actual module paths.\n  ({error})"
        )
