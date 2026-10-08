# Spec: EC Detail View (implementation)

## Objective

Replace the `TemplateView` placeholder `ECDetailView` with a thin Django `DetailView`
following the `ReleaseDetailView` pattern, so the existing `templates/backlog/ec_detail.html`
renders real data: `ec`, `status_badge_class`, `timeline`.

- As a logged-in visitor, I open an EC from the list/dashboard and see its real data.
- As a logged-in visitor, I see a timeline derived from the models: creation, version
  uploads, CD decisions — oldest first.
- As a visitor without a session, I am redirected to the login page.
- A bad pk returns 404.

This spec covers **only the view layer**. The page design, sections, and data contract are
already fixed by `.opencode/specs/EC_DETAIL.md` (approved 2026-10-01); the template is done
and stays **unchanged**.

**Out of scope:** template edits, new URLs, model/migration changes, writes of any kind,
automated tests (see Testing Strategy), permissions beyond "is logged in".

## Decisions (agreed 2026-10-06)

1. **`LoginRequiredMixin`** on `ECDetailView` — supersedes `EC_DETAIL.md` Assumption 1
   ("page stays public until accounts lands"). `accounts` has landed; detail pages now
   require a session.
2. **New focused spec** (`EC_DETAIL_VIEW.md`) rather than editing `EC_DETAIL.md` — that
   spec defined the whole page; this one scopes the implementation slice.
3. **Timeline builder lives in `apps/backlog/selectors.py`** — `build_ec_timeline(ec)` +
   a tiny `_display_name(user)` helper. Keeps the view thin (ARCHITECTURE §4). Supersedes
   the "no selectors.py until a second caller" line in `EC_DETAIL.md` Code Style.
4. **Decision labels in Portuguese**: `"Aprovado"` / `"Rejeitado"` (local map in the
   selector; the `Review` model choices stay English — no `workflow` change).
5. **Template unchanged** — `templates/backlog/ec_detail.html` as committed.
6. **Timeline order: oldest first** — follows `EC_DETAIL.md` Decision 3 (the approved
   decision; its Assumption 5 saying "newest first" is the stale one).
7. **Automated tests, TDD — red first** (agreed 2026-10-06, second thought). Supersedes
   `EC_DETAIL.md` Decision 4 (manual only): ARCHITECTURE §9 makes failing-test-first the
   default, and `RELEASE_DETAIL.md` Decision 3 already chose TDD over manual for the
   sibling page. Because ARCHITECTURE §5 covers **test modules too**, the suite splits:
   - `apps/backlog/tests/test_views.py` → `class TestECDetail` (no `Review` involved);
    - `apps/workflow/tests/test_ec_detail_timeline.py` → decision events (`workflow` sits
      at the top of the arrow chain, so it may read everything below it — same precedent
      as `test_dashboard_decisions.py`).
8. **Timeline line geometry fixed in `static/css/app.css`** (2026-10-06, after visual
   review with headless-Chromium screenshots). The line was the `<ul>`'s `border-left`,
   which spans the whole box: it ran 6px beside the dot centers, 12px above the first
   dot, and past the last one. Now each `<li>` draws its own `::after` segment from its
   dot's center to the next dot's center, `:last-child` draws none, and the dot carries
   `z-index: 1` so the line passes behind it. Pure CSS — the template stays untouched.

## Assumptions

1. The template's context contract is `ec`, `status_badge_class`, `timeline`
   (`event.title`, `event.who`, `event.when`, `event.note`) — verified against the
   committed template.
2. `EC_BADGE_CLASSES` (`apps/backlog/tables.py`) is keyed by `EC.status` value, same map
   the list page uses; fallback `"text-bg-secondary"`.
3. Reviews are reached by traversing `version.review` (reverse one-to-one) at runtime —
   **no `from apps.workflow...` import** (import direction `workflow → documents →
   backlog → accounts`, never upward). Precedent: `requester_dashboard` already traverses
   `versions__review__*`.
4. `DocumentVersion.Meta.ordering = ["-id"]` governs the Documents card (newest first);
   the timeline is sorted separately in the selector.
5. Missing objects on the reverse o2o (`version.review` absent) raise
   `RelatedObjectDoesNotExist` (an `ObjectDoesNotExist` subclass) → skipped, no event.
6. Full suite before this work: `118 passed, 2 failed` — the 2 failures are the
   pre-existing `seed_dashboard_demo` ones (dashboard PR #32), not ours to fix here.

## Tech Stack

Django 6.1, Bootstrap 5 + Inter (already in place). No new dependencies.

## Commands

```bash
uv run ruff format apps/backlog/ && uv run ruff check apps/backlog/
uv run python manage.py check
uv run pytest                                     # full suite stays 118 passed, 2 pre-existing failures
uv run python manage.py runserver                 # manual: log in → /backlog/detail_ec/<pk>/
```

## Project Structure

```
apps/backlog/
├── views.py            # ECDetailView: TemplateView → DetailView (+ LoginRequiredMixin)
├── selectors.py        # + build_ec_timeline(ec), _display_name(user)
└── tables.py           # unchanged — EC_BADGE_CLASSES imported from here
templates/backlog/
└── ec_detail.html      # UNCHANGED
```

## Code Style

The view mirrors `ReleaseDetailView` — model/template/context_object_name, a decorated
queryset, and one context method that delegates derivation to a selector:

```python
class ECDetailView(LoginRequiredMixin, DetailView):
    model = EC
    template_name = "backlog/ec_detail.html"
    context_object_name = "ec"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("requester", "responsible_cd", "release")
            .prefetch_related("versions__uploaded_by", "versions__review")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ec = self.object
        context["status_badge_class"] = EC_BADGE_CLASSES.get(ec.status, "text-bg-secondary")
        context["timeline"] = build_ec_timeline(ec)
        return context
```

The selector derives the timeline from the models only — no new queries beyond the
prefetch:

```python
def build_ec_timeline(ec) -> list[dict]:
    """Events (creation, uploads, CD decisions) for one EC, oldest first — EC_DETAIL Decision 3."""
    events = [{
        "title": "EC criada",
        "who": _display_name(ec.requester),
        "when": ec.created_at,
        "note": None,
    }]
    for version in ec.versions.all():
        events.append({
            "title": f"Documento {version.version_number} carregado",
            "who": _display_name(version.uploaded_by),
            "when": version.uploaded_at,
            "note": version.change_reason or None,
        })
        try:
            review = version.review
        except ObjectDoesNotExist:
            continue
        events.append({
            "title": f"Decisão do CD: {DECISION_LABELS.get(review.decision, review.get_decision_display())}",
            "who": _display_name(review.cd),
            "when": review.decided_at,
            "note": review.comment or None,
        })
    events.sort(key=lambda event: event["when"])
    return events
```

`DECISION_LABELS = {"approved": "Aprovado", "rejected": "Rejeitado"}` (Decision 4).
`who` is `full_name or username`, `None` when the FK is null — the template already
guards `{% if event.who %}`.

**Why `select_related`/`prefetch_related` is not decoration:** the header renders three
FK columns (`requester`, `responsible_cd`, `release`), the Documents card renders
`versions` + `uploaded_by`, and the timeline renders `version.review` + `review.cd`.
Without the decorations that is a query per relation per row.

## Testing Strategy

**pytest-django + factory-boy, written before the view** per
`.opencode/skills/django-tdd-loop/SKILL.md` — failing test first (red), minimal code
(green), then refactor. Status key: ✅ = passing (all 14 green as of 2026-10-06).

**`apps/backlog/tests/test_views.py` → `class TestECDetail`** (same `pytestmark`,
`Test...` grouping):

1. ✅ Anonymous GET → 302 to `accounts:login` (`LoginRequiredMixin`).
2. ✅ Logged in → 200, `response.context["ec"] == ec`.
3. ✅ Unknown pk → 404.
4. ✅ Page shows real data: `EC-{ec_code}`, reference, description, requester full name,
   release code.
5. ✅ `status_badge_class` in context matches `EC_BADGE_CLASSES` (`in_validation` →
   `text-bg-warning`) and renders in the badge markup.
6. ✅ EC with no versions renders the Documents empty state ("Ainda sem documentos").
7. ✅ An uploaded version renders: version number + "enviado por" (reverse-manager
   helper — no `documents` import in the test).
8. ✅ Timeline context exists; first event is "EC criada" with requester, `created_at`.
9. ✅ Upload events after creation, oldest first; `change_reason` surfaces as `note`.
10. ✅ Creation date renders `Criada em d/m/Y às H:i`.
11. ✅ Query count constant as version count grows (3 → 7) — guards
    `select_related`/`prefetch_related`; anchored on `context["ec"]` so it is red on day one.

**`apps/workflow/tests/test_ec_detail_timeline.py`** (decision events; §5 covers test
modules — same split as `test_dashboard_decisions.py`):

12. ✅ Approval renders "Decisão do CD: Aprovado" (PT label) with CD, `decided_at`, comment.
13. ✅ Rejection renders "Decisão do CD: Rejeitado" with its comment as note.
14. ✅ Decision event sorts after the upload, oldest first:
    `["EC criada", "Documento v1.0 carregado", "Decisão do CD: …"]`.

The pre-existing suite stays green (baseline `118 passed, 2 known
`seed_dashboard_demo` failures`).

## Boundaries

- **Always:** TDD (red → green → refactor), thin view (derivation in selectors),
  `DetailView` pattern mirroring `ReleaseDetailView`, runtime traversal for
  `version.review`, 404 for missing pk, `uv run pytest` + `uv run ruff` +
  `manage.py check` before done.
- **Ask first:** touching `templates/backlog/ec_detail.html`, model/migration changes,
  permissions beyond login (per-object visibility like `_visible_ecs`), new
  dependencies.
- **Never:** import `apps.workflow` into `backlog`, change `EC.status` (ARCHITECTURE §6 —
  workflow only), write anything from this page (read-only), drop `LoginRequiredMixin`.

## Success Criteria

- Tests 1–14 written first and confirmed **red**; then all green; full suite at
  `118 + 14` passed with only the 2 pre-existing `seed_dashboard_demo` failures; ruff
  and `manage.py check` clean.
- `ECDetailView` is a `LoginRequiredMixin` + `DetailView` with
  `context_object_name = "ec"`; view contains no timeline-building logic of its own.
- `build_ec_timeline` lives in `selectors.py`, returns oldest-first events with PT
  decision labels; no `workflow` import anywhere in the change (including tests —
  decision events live in `apps/workflow/tests/`).
- Template byte-identical (no diff on `templates/backlog/ec_detail.html`).
- Timeline line passes through the dot centers and starts/ends exactly at the first/last
  dot (Decision 8), verified with headless-Chromium screenshots.
- No model change, no migration, no writes.

## Open Questions

- None blocking. All five answers recorded as Decisions 1–5 above.
