# Spec: Release Detail Page

## Objective

`/backlog/detail_release/<int:pk>/` shows one Release and the ECs grouped under it.

- As a visitor, I click a release in the list and see that release's identity: code, year,
  sequence, occupancy (`2 / 10`), status badge, go-live date, creation timestamp.
- As a visitor, I see the ECs belonging to **that** release and no others — reference,
  description, requester, CD, creation date, status, origin.
- As a visitor, I get a 404 for a release that does not exist (not a crash, not an empty page).
- As a visitor, a release with no ECs shows a clean empty state.

**Why this page exists — it is not in the SRD.** The SRD has no "view a Release" requirement.
RF02 defines the one-to-many Release→EC relation, and RF12 asks for backlog filtering
*by Release*. This page is the simplest honest way to satisfy "show me this Release's ECs",
and it is Deferred item 3 in `RELEASE_MODULE.md`, where it was recorded as the moment
`release_with_ec_count()` gets its **second caller**.

**Out of scope:** any write — no status change, no go-live entry (RF04 belongs to `workflow`,
§7.6), no creating or reassigning ECs, no filters, no permissions/login, no documents.

## Assumptions

1. **Public, read-only** until `accounts` / RNF01 lands — same decision as the list page and
   `EC_DETAIL.md`.
2. `DetailView`, `context_object_name = "release"`, URL kwarg `pk` (Django convention).
3. Bad pk → **404**, not a crash and not an empty 200.
4. The release's own numbers come from the **annotation** (`ec_total`), never from the
   `ec_count` property — the N+1 lesson already paid for in `RELEASE_MODULE.md` test #8.
5. Status badge uses the **same precedence as the list**: fullness wins over `is_open`
   (closed + full → "Lotado"). One rule, two pages, one test each.
6. Dates render as `d/m/Y` (go-live, `—` when null) and `d/m/Y H:i` (created) —
   `LANGUAGE_CODE` is `en-us`, so no localized month names.

## Decisions (agreed 2026-10-02)

1. **Reuse `ECTable` unchanged.** Consequence accepted: the `Release` column repeats the same
   release name on every row of a page that is already about that release. Revisit when the
   table is reused somewhere it matters. This keeps the slice small — no second table class.
2. **URL path is `detail_release/<int:pk>/`, not `release/<int:pk>/`.** Agreed 2026-10-05:
   the codebase already ships `detail_ec/<int:pk>/`, so `detail_ec`/`detail_release` stays
   symmetric. The `name="release_detail"` (used by `{% url %}`/`reverse`) is unchanged.
3. **Automated tests, TDD.** Deviation from `EC_DETAIL.md` (which chose manual verification)
   in favour of the ARCHITECTURE §9 default. Red test first, then the view.
4. **Navigation:** the release code in the list becomes the link to the detail page, and the
   `action` column is **deleted** from `ReleaseTable`. This closes Outstanding item 1 of
   `RELEASE_MODULE.md` (the dead `href="#"`) in the same PR.

## Tech Stack

Django 6.1, django-tables2 (reusing `ECTable`), Bootstrap 5 + Inter. No new dependencies.

## Commands

```bash
uv run pytest apps/backlog/tests/ -q     # release list + detail tests
uv run pytest                            # full suite
uv run ruff check . && uv run ruff format apps/backlog/
uv run python manage.py runserver        # manual: /backlog/release/ → click a code
```

## Project Structure

```
apps/backlog/
├── views.py            # ReleaseDetailView(DetailView) + ReleaseListView link
├── urls.py             # detail_release/<int:pk>/  name="release_detail"
├── tables.py            # ReleaseTable: code → link, action column deleted
└── tests/
    ├── test_views.py   # new tests (see Testing Strategy)
    └── factories.py    # existing ReleaseFactory / ECFactory
templates/backlog/
├── release_list.html   # unchanged (renders the table)
└── release_detail.html # NEW — header card + {% render_table table %}
```

## Code Style

Thin view; the query stays in the view and is the second caller of the selector:

```python
class ReleaseDetailView(DetailView):
    template_name = "backlog/release_detail.html"
    context_object_name = "release"

    def get_queryset(self):
        return release_with_ec_count()          # annotate(ec_total=Count("ecs"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = ECTable(self.object.ecs.select_related(
            "release", "requester", "responsible_cd",
        ))
        RequestConfig(self.request).configure(table)   # sort + paginate like the list page
        context["table"] = table
        return context
```

**The `select_related` is not decoration — it is the whole N+1 story for this page.**
`ECTable` renders three FK columns (`release`, `requester`, `responsible_cd`), each of which
costs one query per EC row without it. With it: one query, regardless of row count.

The link in the list uses the URL name, never a hardcoded path:

```python
release_code = tables.TemplateColumn(
    verbose_name="Release",
    orderable=False,
    template_code="""<a href="{% url 'backlog:release_detail' record.pk %}"
                       class="fw-semibold text-decoration-none">{{ record.release_code }}</a>""",
)
```

## Testing Strategy

pytest-django + factory-boy, in `apps/backlog/tests/test_views.py` (same class, same
`pytestmark`), **written before the view** per `.opencode/skills/django-tdd-loop/SKILL.md`.

Status key: ⏳ all pending — this spec is not yet approved.

1. ⏳ `GET /backlog/detail_release/<pk>/` returns 200 for an existing release.
2. ⏳ A bad pk returns **404**.
3. ⏳ The page shows an EC belonging to this release, and **does not** show an EC belonging
   to a different release (proves the filter is real, not "all ECs").
4. ⏳ The header shows the annotated occupancy `ec_total / capacity` and the status badge
   matching the list page's rule (full + open → "Lotado").
5. ⏳ A release with zero ECs renders the empty state, not a crash.
6. ⏳ **No N+1:** query count constant as the EC count grows — this is the test that fails if
   `select_related` is dropped from `get_context_data()`, and it is the exact test that caught
   `ec_count` on the list page (`12 == 5`).
7. ⏳ On the list page, a release's code links to `reverse("backlog:release_detail",
   args=[release.pk])`, and `ReleaseTable` no longer declares or lists an `action` column.

## Boundaries

- **Always:** TDD (red → green), `uv run pytest` + ruff before done, thin views, 404 for
  missing objects, `select_related` for FK columns rendered by a table.
- **Ask first:** model/migration changes, new dependencies, filters, auth/permissions,
  touching `documents`/`workflow`/`accounts`, adding a second table class for this page.
- **Never:** write anything on this page (`is_open`, `capacity`, `status`,
  `production_go_live_date` — all writes belong to services/workflow), import `workflow` or
  `documents` models into `backlog`, call the `ec_count` property inside a loop, leave a
  dead `href="#"` anywhere.

## Success Criteria

- `/backlog/detail_release/1/` renders that release's header and **only** its ECs; no hardcoded
  values in `release_detail.html`.
- A bad pk returns 404; an empty release returns a clean empty state.
- Query count does not grow with the number of EC rows.
- The release code on the list page navigates to the detail page; `ReleaseTable` has no
  `action` column (Outstanding item 1 of `RELEASE_MODULE.md` → ✅).
- New tests pass, the existing 53 stay green, `ruff check` clean, no model change, no
  migration, no writes.

## Deferred

- `ReleaseTable` Go-live and Criado em columns (`RELEASE_MODULE.md` Outstanding #2).
- `test_selectors.py` and list tests 5, 6, 7, 9 (RELEASE_MODULE tests ⏳).
- Hiding `ECTable`'s redundant `Release` column (Decision 1 above).

## Open Questions

- None blocking. If you want the `Release` column dropped after all, say so before
  implementation — it changes Decision 1 and the test count, not the architecture.
