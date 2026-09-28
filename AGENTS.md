# AGENTS.md — EC Backlog Management System

**Before doing any work in this repository, read and follow `docs/ARCHITECTURE.md`.**

The ARCHITECTURE.md file is the single source of truth for:
- Project structure and app responsibilities
- Dependency rules (import direction)
- Code conventions (services/selectors, thin views)
- Domain rules (EC IDs, Release capacity, status transitions, versioning)
- Database/migration requirements
- Testing standards (TDD loop)
- Security and production checklist

If a request conflicts with ARCHITECTURE.md, stop and ask the user instead of silently breaking the rules.

## Quick reference

| Area | Rule |
|------|------|
| Package manager | **uv only** — never pip, venv, requirements.txt |
| Python version | Pinned in `.python-version` — do not change |
| App structure | All apps under `apps/` with `name = "apps.<app>"` |
| Import direction | `workflow → documents → backlog → accounts` (never upward) |
| Business logic | In `services.py` / `selectors.py`, not views |
| Status changes | Only via `workflow` services, never direct assignment |
| Migrations | Follow `.opencode/skills/django-db-integrity/SKILL.md` |
| New features | Spec first (`.opencode/skills/spec-driven-development/SKILL.md`), wait for `SPEC_APPROVED` |
| Testing | TDD: failing test → minimal code → refactor (`.opencode/skills/django-tdd-loop/SKILL.md`) |
| Commands | Always `uv run python manage.py ...` |

## Required files to check before starting

1. `docs/ARCHITECTURE.md` — full architecture and rules
2. `docs/System_Requirements_EC_Backlog_Management_EN_v1_1.pdf` — SRD (source of truth for requirements)
3. `pyproject.toml` / `uv.lock` — current dependencies
4. `.python-version` — Python version