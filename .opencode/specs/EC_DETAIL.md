# Spec: EC Detail Page

## Objective

`/backlog/detail_ec/<pk>/` shows the real EC record instead of hardcoded HTML.

- As a visitor, I open an EC from the list and see its real data: code, reference, description, release, requester, CD, status, creation timestamp.
- As a visitor, I see the document versions attached to that EC (read-only).
- As a visitor, I see a timeline of what happened to that EC: creation, version uploads, CD decisions.
- As a visitor, I get a proper 404 for an EC that does not exist (not a crash, not an empty page).

**Out of scope:** uploading documents, editing, cancelling, any status change, permissions/login, auditlog-driven timeline.

## Assumptions

1. Page stays **public** until `accounts` lands (same decision as the list page).
2. View becomes Django's `DetailView` (`model = EC`, `context_object_name = "ec"`) instead of `TemplateView`.
3. URL kwarg renamed `ec_id` → `pk` (Django convention; `DetailView` looks up `pk`).
4. Documents section renders **existing** versions read-only; empty state says "sem documentos".
5. Timeline is **derived from the models** (EC, versions, reviews), newest first — not from auditlog.
6. The action buttons (Editar / Cancelar) are **hidden** for now: they are workflow writes and need accounts + permissions.
7. Dates render with explicit numeric formats (`d/m/Y H:i`) — `LANGUAGE_CODE` is `en-us`, so no localized month names.

## Template mismatches (need a decision — see Open Questions)

`ec_detail.html` is a static mock and asks for data the model does not have:

| Template asks | Model reality |
|---|---|
| "Título" | no title field — closest is `reference` (`CR2026003`) |
| "Descrição" | `description` ✓ |
| "EC-2026-001" in header | `ec_code` is `2026-001` (no `EC-` prefix) |
| "Documentos" card | placeholder text; model has `versions` ✓ |
| "Histórico" timeline (5 hardcoded events) | no event table — derived from models |
| Editar / Cancelar buttons | workflow writes — out of scope |

## Tech Stack

Django 6.1, django-tables2 not needed here (one record, not a list), Bootstrap 5 + Inter (already in place).

## Commands

```bash
uv run pytest apps/backlog/tests/test_views.py   # detail tests
uv run pytest                                     # full suite
uv run ruff check . && uv run ruff format .
uv run python manage.py runserver                 # manual: /backlog/ec/ then click "Ver"
```

## Project Structure

```
apps/backlog/
├── views.py            # ECDetailView → DetailView
├── urls.py             # detail_ec/<int:pk>/
└── tests/
    ├── test_views.py   # new tests (see Testing Strategy)
    └── factories.py    # existing factories
templates/backlog/
└── ec_detail.html      # replace hardcoded values with {{ ec.* }} / {% for %} loops
```

## Code Style

Thin views; the queryset stays in the view for now (same call as the list page — no `selectors.py` until a second caller appears).

```python
class ECDetailView(DetailView):
    model = EC
    template_name = "backlog/ec_detail.html"
    context_object_name = "ec"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "requester", "responsible_cd", "release"
        ).prefetch_related("versions__uploaded_by")
```

## Testing Strategy

**Manual verification only** (user decision, 2026-10-01) — deviation from ARCHITECTURE §9, recorded above.

Manual checklist:
1. `/backlog/detail_ec/1/` → 200, real data for EC 2026-001 (which has 1 document version).
2. `/backlog/detail_ec/999999/` → 404 page.
3. The EC list "Ver" link lands on the right EC.
4. EC without versions shows the empty state.
5. Devtools: no template errors, no N+1 warning spam; query count logged via `connection.queries` with `DEBUG=True`.


## Boundaries

- **Always:** TDD if tests are in scope, `uv run pytest` + ruff before done, thin views, 404 for missing objects.
- **Ask first:** changing `ec_detail.html` layout/sections, new dependencies, model/migration changes, touching `documents`/`workflow` apps.
- **Never:** change `EC.status` here (ARCHITECTURE §6 — workflow only), import `documents` or `workflow` models into `backlog` (import direction), enable Editar/Cancelar without permissions.

## Success Criteria

- `/backlog/detail_ec/1/` renders that EC's real data; no hardcoded values remain in the template.
- A bad pk returns 404.
- Documents list shows real versions, or a clean empty state.
- Timeline shows real events (creation, uploads, decisions) — or is removed if the user prefers to defer it.
- No status changes, no uploads, no permission logic. `manage.py check` clean, ruff clean.

## Decisions (approved 2026-10-01)

1. **"Título" field is dropped** — the model has no title and `reference` is already shown in the list. Template keeps Descrição only.
2. **EC code displays prefixed**: `EC-{{ ec.ec_code }}` → `EC-2026-001` (matches the approved mock design; the list page still shows the plain code — align later if desired).
3. **Timeline is derived from the models now** — creation, version uploads, CD decisions, oldest first (matches the mock's reading order).
4. **No automated tests for this feature — manual verification only.** Recorded deviation from ARCHITECTURE §9, chosen by the user on 2026-10-01. Consequence accepted: no regression net for this view; the view is thin, so risk is limited to template wiring.

## Known limitations (accepted for this feature)

- **No "CD atribuído" event**: the model stores `responsible_cd` but no assignment timestamp, so that timeline entry cannot be dated honestly. It is omitted rather than faked.
- **No "Em validação" event**: status-change timestamps are not stored (no status history table, no auditlog query yet). The current status is shown in the header badge.
- **Document download links** point at `MEDIA_URL`; serving media in production is not configured yet (`production.py` has no media/static serving yet) — links work in dev.

