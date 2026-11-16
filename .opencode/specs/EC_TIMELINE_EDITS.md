# Spec: EC Timeline — show "EC editada" events (implementation)

## Objective

Make the Histórico timeline on the EC detail page also show that the EC was
edited: one "EC editada" event per auditlog `UPDATE` entry on the EC, merged
chronologically with the existing events. The timeline stays derived from
models + auditlog; the template is unchanged.

- As a logged-in visitor viewing an EC that was edited after creation, I see an
  "EC editada" entry between the events it happened between (oldest first),
  with who edited it, when, and which fields changed.
- An EC that was never edited looks exactly as before.
- The CD decision flow does not gain duplicate events.

This supersedes the "derived from the models only" line in
`EC_DETAIL_VIEW.md` (Decision 3's docstring): auditlog is a third-party package
(`from auditlog.models import LogEntry` — already imported in
`apps/backlog/selectors.py` line 3), so the import direction
`workflow → documents → backlog → accounts` (ARCHITECTURE §5) is untouched.

**Out of scope:** template edits, model/migration changes, new URLs, status
transition events (`sent_to_des`, `closed`, `cancelled`) as their own timeline
entries (follow-up spec if wanted), the admin audit-log pages.

## Requirements traced

- RNF02 (audit trail) is the data source; this feature only **surfaces** it on
  the EC detail page. No SRD § 7 field is added or changed.
- No RF covers the timeline rendering; this is a presentation gap surfaced in
  review of `EC_DETAIL.md` ("no event table — derived from models"), approved
  by the user in conversation (Option A chosen, 2026-11-16).

## Decisions

1. **Source: auditlog `LogEntry`, not new model fields.** `EC` is already
   registered (`auditlog.register(EC)`, `apps/backlog/admin.py:48`) and
   `test_editing_an_ec_records_the_actor` (apps/backlog/tests/test_auditlog.py)
   proves UPDATE entries carry the acting user. A `edited_at`/`edited_by` field
   would keep only the *last* edit — strictly less data for a migration's cost.
2. **One extra query, scoped and indexed.** `LogEntry.objects.for_object(ec)`
   (auditlog's manager helper; filters on indexed `content_type` + `object_pk`)
   + `.filter(action=UPDATE)` + `.select_related("actor")`. Called once per
   detail request from `build_ec_timeline` — never in lists. Result set is
   bounded by how many times *this one EC* was touched.
3. **Status-only UPDATE entries are skipped.** Status transitions to
   `approved`/`rejected` are already rendered as "Decisão do CD" (model-derived,
   selectors.py:284-296); rendering them again from auditlog would duplicate.
   Transitions to `sent_to_des`/`closed`/`cancelled` stay unrendered (out of
   scope). Rule: a `status` key is removed from the change summary; if no other
   changed field remains, the entry produces **no** event.
4. **PT field labels** for the change summary (the UI is Portuguese, same
   precedent as `EC_STATUS_PT`, selectors.py:440):
   `reference → "Referência"`, `description → "Descrição"`,
   `release_id → "Release"`, `responsible_cd_id → "CD responsável"`.
   Unknown keys fall back to the raw key.
5. **Values shown only for `reference`.** auditlog's `changes` dict stores
   stringified old/new pairs. `"CR2026042" → "CR2026123"` reads well; FK fields
   store raw pks (`"3" → "5"` — meaningless without extra queries) and
   `description` can be paragraph-length. So: `reference` shows
   `Referência: "old" → "new"`; every other field shows only `Label alterada`.
6. **Ordering stays the existing sort.** Edits are appended to `events` before
   the final `events.sort(key=lambda event: event["when"])` (selectors.py:297).
   All `when` values are timezone-aware datetimes (model fields + auditlog
   `timestamp`), so comparison is safe; Python's stable sort keeps
   "EC criada" above "Documento v1.0 carregado" on same-millisecond ties.
7. **TDD, red first** (ARCHITECTURE §9). New tests live in
   `apps/backlog/tests/test_views.py` (edit flow needs no `workflow` object);
   one guard test goes to `apps/workflow/tests/test_ec_detail_timeline.py` to
   assert the decision flow gains no "EC editada" duplicate.
8. **Template unchanged.** The event contract (`title`, `who`, `when`, `note`)
   and `templates/backlog/ec_detail.html` stay as committed.

## Assumptions

1. `LogEntry.objects.get_for_object(ec)` exists in auditlog 3.4.1 (verified:
   indexed `content_type` + `object_id/object_pk` filter; the auditlog docs'
   name `for_object` is wrong for this version — Assumption 1's fallback was
   checked and `get_for_object` is the real API).
2. `entry.changes` is a `{field: (old, new)}` dict for UPDATE entries (matches
   `_changed()`, selectors.py:467).
3. Baseline before this work: **374 passed, 1 failed** — the failure
   (`test_blank_description_is_rejected`) is pre-existing uncommitted work
   (`description` nullable, apps/backlog/models.py:67 + migration 0003) and
   must not be touched or fixed here.

## Tech Stack

Django 6.1, django-auditlog (already installed). No new dependencies.

## Project Structure

```
apps/backlog/
├── selectors.py        # + _EDIT_FIELD_LABELS_PT, _edit_note(changes); build_ec_timeline merges edit events
└── tests/
    └── test_views.py   # + edit-timeline tests (TestECDetail class area)
apps/workflow/tests/
└── test_ec_detail_timeline.py   # + guard: decision flow has no "EC editada"
templates/backlog/
└── ec_detail.html      # UNCHANGED
```

## Selector sketch

```python
_EDIT_FIELD_LABELS_PT = {
    "reference": "Referência",
    "description": "Descrição",
    "release_id": "Release",
    "responsible_cd_id": "CD responsável",
}

def _edit_note(changes: dict) -> str | None:
    """Readable PT summary of an EC edit; `status` never appears here."""
    parts = []
    for field, (_old, new) in changes.items():
        if field == "status":
            continue
        label = _EDIT_FIELD_LABELS_PT.get(field, field)
        if field == "reference" and new:
            parts.append(f"{label}: \"{new}\"")          # auditlog `new` is the value
        else:
            parts.append(f"{label} alterada")
    return "; ".join(parts) or None

def build_ec_timeline(ec) -> list[dict]:
    events = [...]  # existing: creation, uploads, decisions
    edits = (
        LogEntry.objects.get_for_object(ec)
        .filter(action=LogEntry.Action.UPDATE)
        .select_related("actor")
    )
    for entry in edits:
        note = _edit_note(entry.changes if isinstance(entry.changes, dict) else {})
        if note is None:          # status-only save (workflow transition)
            continue
        events.append({
            "title": "EC editada",
            "who": _display_name(entry.actor),
            "when": entry.timestamp,
            "note": note,
        })
    events.sort(key=lambda event: event["when"])
    return events
```

(Exact `_edit_note` wording may shift while TDD-ing; the Decisions above are
the contract.)

## Test Plan (failing first)

`apps/backlog/tests/test_views.py` — new class `TestECDetailTimelineEdits`:

1. **edited EC shows the event** — requester POSTs `ec_edit` (change
   `reference`), GETs `ec_detail`: timeline contains "EC editada" with the
   requester's name and the new reference in the note.
2. **no edits → no event** — unedited EC's timeline has no "EC editada".
3. **edit sorts chronologically** — create (t0) → upload v1.0 (t0+x) → edit
   (t0+2x): titles order is `["EC criada", "Documento ... carregado",
   "EC editada"]`.
4. **multi-field edit note** — edit `reference` + `description` (+
   `responsible_cd` unchanged case): note lists both labels, no raw pk text,
   no `status`.
5. **status-only entry skipped** — approve the EC (status UPDATE entry via
   workflow): timeline gains no "EC editada".

`apps/workflow/tests/test_ec_detail_timeline.py` — guard:

6. **decision flow unchanged** — existing approve/reject tests keep passing
   unchanged (no duplicate decision events introduced).

## Commands

```bash
uv run pytest apps/backlog/tests/test_views.py -k TimelineEdits   # red first
uv run pytest                                                    # full suite ≥ baseline
uv run ruff format apps/backlog && uv run ruff check apps/backlog
uv run python manage.py check
```

## Acceptance Criteria

- [ ] Edited ECs show "EC editada" events, oldest first, merged with existing events.
- [ ] Who / when / which-fields render; `status` never leaks into a note.
- [ ] Decision flow timeline is byte-identical to today's for unedited flows.
- [ ] Template and models untouched; no migration.
- [ ] Full suite at or above baseline (374 passed + new tests; the 1 pre-existing
      failure stays the only failure).
