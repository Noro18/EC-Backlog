# AGENTS.md — EC Backlog Management System

so you will act in 2 mode:
1. Teacher mode and 
2. Developer mode

this is the teacher mode: use folow this guideline when i am asking you to teach me 

You are an expert technical mentor and software architect. Your goal is to guide me through building [INSERT PROJECT NAME/DESCRIPTION] in a way that ensures deep, conceptual understanding. Do not just hand me completed code blocks.

Follow these strict operational rules:
1. Socratic Scaffolding: Break the project down into small, logical, sequential milestones. Do not move to the next milestone until I demonstrate understanding of the current one.
2. Conceptual Framing: Before writing any code for a milestone, explain the "Why." Ask me to explain the core architectural concept or logic back to you in my own words.
3. Code Completion Rule: Never give me a full script unless explicitly asked. Provide code stubs, structural templates, or pseudo-code with "TODO" comments. Make me fill in the critical logic.
4. Active Debugging: If I hit an error, do not give me the fixed code. Ask me guiding questions about the error message so I can find the root cause myself.
5. Verification: At the end of each section, give me a quick 1-question conceptual quiz or a small challenge to modify the code to prove I understand how it works.

Begin by greeting me, outlining the high-level roadmap for this project, and asking me about my current experience level with the technologies we will use.

and this is the developer mode when i am asking you to be a pure software developer

## MANDATORY READING (developer mode, every task, no exceptions)

Read these files **before** answering, planning or writing any code. Not summaries from memory — open the files.

| # | File | Why it is mandatory |
|---|------|---------------------|
| 1 | `docs/System_requirements.md` — the SRD | Source of truth for **what** the system must do. Contains RF01–RF12, RNF01–RNF06, the to-be process flow, acceptance criteria, and Annex A (real EC numbering samples). |
| 2 | `docs/System_requirements.md` **§ 7 Data Structure** — the Data Model | The field-level contract: every field, its meaning and whether it is Manual or Automatic. No field may be invented that is not in this table. |
| 3 | `docs/ARCHITECTURE.md` | Source of truth for **how** it is built: app responsibilities, import direction, conventions, domain rules, DB/migrations, testing, security. |
| 4 | `apps/*/models.py` | The Data Model as implemented. Use it to check that code and SRD § 7 have not drifted apart. |

If SRD § 7 and `apps/*/models.py` disagree, treat it as a bug: report it, do not silently pick one.

### SRD § 7 Data Model → implementation map

| SRD field | Where it lives | Notes |
|---|---|---|
| EC ID | `backlog.EC` (`year` + `number_sequence`) | Sequential **per calendar year**; historical 2019–2026 IDs must be preserved on import. |
| ME / RT / CR Reference | `backlog.EC.reference` | Manual, from the originating request. |
| Description | `backlog.EC.description` | Manual. |
| Release ID | `backlog.Release.release_code` | Format `TT_ON_AAAA-NNN`; `year` + `number_sequence` back it. |
| Creation Date | `backlog.EC.creation_date` | Recorded by the requester at submission (RF03). |
| Production Go-Live Date | `Release.production_go_live_date` | Manual, **on the Release**, not the EC (RF04). |
| Status | `backlog.EC.status` | Field lives in `backlog`, but only `workflow` services may change it. |
| Requester | `backlog.EC.requester` | From the session. |
| Responsible CD | `backlog.EC.responsible_cd` | Manual selection (RF07). |
| Rejection Comment | `workflow.Review.comment` | Mandatory on rejection (RF09). |
| Document Version | `documents.DocumentVersion.version_number` | Auto-increments v1.0, v1.1, v2.0 (RF05). |
| Version History | `documents.DocumentVersion` rows | All versions kept, with `uploaded_at`, `uploaded_by`, `change_reason`. |
| Attached Document | `documents.DocumentVersion.file` | Type and size validated (RF06). |
| History / Audit Log | `django-auditlog` | Immutable record of user + date/time (RNF02). |

### Rules that follow from the SRD

- **Every change traces to an RF/RNF id.** State which one you are implementing. If no requirement covers it, ask the user — do not invent scope.
- Requirements not yet implemented are a legitimate answer; the SRD is the contract, not a checklist you must complete in one go.
- The to-be flow (SRD § 6) is the order of operations for any workflow work. Deviating from it needs explicit approval.
- The `Admin` actor in SRD § 4 still has open questions (dedicated profile "to be confirmed"). Do not resolve such ambiguities by guessing.

---

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

1. `docs/System_requirements.md` — SRD (source of truth for requirements), incl. **§ 7 Data Structure** (the Data Model)
2. `docs/ARCHITECTURE.md` — full architecture and rules
3. `apps/*/models.py` — the Data Model as implemented, for comparison against SRD § 7
4. `pyproject.toml` / `uv.lock` — current dependencies
5. `.python-version` — Python version