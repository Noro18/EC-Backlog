# Spec: On-demand Release creation ("+ Kria Release Foun") — RF02 slice

## Objective

Today a requester can only attach an EC to a Release that already exists
(created via the admin panel). If every open Release is full — or the
requester simply wants a fresh Release — they are stuck (**RF02** says the
system must *generate* the Release ID, not only reuse existing ones).

- As a requester, I open Nova Solicitação, click the Release dropdown, see
  `+ Kria Release Foun` as the last option, pick it, submit — and my EC lands
  on a brand-new Release whose code continues the sequence automatically
  (e.g. last was `TT_ON_2026-003` → mine becomes `TT_ON_2026-004`).
- As a requester, I can do this **even when older Releases still have room**
  (001, 002 half-empty) — the option is always present, not only as a
  fallback when nothing is open.
- As a requester, I never type a Release code — generation stays automatic
  (RF02), capacity stays 10, format stays `TT_ON_AAAA-NNN`.

**Out of scope:** a standalone "manage releases" page, editing capacity,
closing/reopening Releases, typing a Release code manually, importing
Releases. Only creation *as part of EC submission*.

## User decisions (agreed in chat)

1. Option always visible at the bottom of the Release dropdown
   (`+ Kria Release Foun`), matching the mockup — not only when no Release
   is open.
2. Numbering continues from the highest existing sequence of the current
   year (003 → 004), never restarts, never user-typed.
3. Requester (+ Administrator, same gate as `NewECView`) may trigger it.
   No separate permission, no separate page.

## Assumptions

1. **Release year = current year** (`timezone.localdate().year`), same rule
   `create_ec` already uses for the EC's own `year`. A new Release never
   backfills a past year.
2. **Capacity default 10, `is_open=True`** — same defaults as the model;
   the on-demand path does not expose them.
3. `Release.release_code` is derived (`TT_ON_{year}-{n:03d}`), never typed.
   Uniqueness is enforced by the existing DB constraints
   (`release_year_number_uniq` + unique `release_code`).
4. The dropdown keeps showing only open, non-full Releases (current
   `open_releases_with_ec_count()` behaviour) — the new option is appended
   last and is never filtered out.

## Decisions (proposed — confirm before code)

1. **Sentinel option, not a second field (Option A).** The `release` field
   becomes a plain `ChoiceField` whose choices are built in `__init__`:
   `[(pk, "TT_ON_… (aberta — x/10)"), …, ("__new__", "+ Kria Release Foun")]`.
   `clean_release()` returns either a `Release` instance or the sentinel
   `NEW_RELEASE = "__new__"`. Rejected alternative: a separate checkbox
   beside the dropdown (simpler validation, but contradicts the approved
   mockup and splits one decision across two widgets).
2. **One service owns creation: `create_release()`** in
   `apps/backlog/services.py` (thin views — ARCHITECTURE §6). Sketch:
   ```python
   NEW_RELEASE = "__new__"

   def create_release() -> Release:
       """RF02: mint the next Release of the current year. No import upward."""
       with transaction.atomic():
           year = timezone.localdate().year
           for _ in range(3):  # retry on race (see edge cases)
               last = Release.objects.filter(year=year).order_by("-number_sequence").first()
               n = (last.number_sequence + 1) if last else 1
               try:
                   with transaction.atomic():
                       return Release.objects.create(
                           release_code=f"TT_ON_{year}-{n:03d}",
                           year=year, number_sequence=n,
                       )
               except IntegrityError:
                   continue  # someone minted n first; re-read and try n+1
           raise ValidationError("La konsege kria Release; tenta fali.")
   ```
3. **EC + Release in a single atomic unit.** `NewECView.form_valid` wraps:
   `if release is NEW_RELEASE: release = create_release()` then the existing
   `create_ec(...)` call — all inside the current `transaction.atomic()`
   (nested atomics are savepoints; a later document-validation failure rolls
   back the Release too — no orphan Releases).
4. **No import-rule change.** Everything lives in `backlog`
   (`services.py`, `forms.py`, `views.py`) — no upward import, so no
   ARCHITECTURE §5 entry needed.

## System architecture — affected components

```
apps/backlog/
├── services.py      +create_release() + NEW_RELEASE sentinel (RF02)
├── forms.py         release: ModelChoiceField → ChoiceField with dynamic
│                    choices + "+ Kria Release Foun" last; clean_release()
│                    validates PK still open/non-full (existing rule kept)
├── views.py         NewECView.form_valid: mint-then-create inside atomic
└── tests/
    ├── test_services.py  NEW — numbering, year rollover, race retry
    └── test_views.py     +POST with "__new__" slice
templates/backlog/ec_form.html   label/help tweak only (option renders itself)
```

**Database schema changes: none.** `Release` already has every field
(`release_code`, `year`, `number_sequence`, `capacity`, `is_open`);
no model edit, no migration (django-db-integrity skill: verify with
`makemigrations --check --dry-run` anyway).

## Payloads and edge cases

| Case | Expected behaviour |
|---|---|
| POST `release="__new__"`, rest valid | 302; new `Release TT_ON_<year>-<max+1>`; EC linked to it; old Releases untouched |
| Year has no Releases at all | first code is `TT_ON_<year>-001` |
| Two requesters click at once | SQLite write lock serialises; loser hits unique constraint → service retries with re-read `n+1` (max 3 tries, then a "tenta fali" form error, never a 500) |
| POST `release=<pk>` of a full/closed Release | refused as today (`create_ec` ValidationError → form error, 200, nothing created) |
| POST `release=<garbage>` / another year's closed pk | form error (choice not in dropdown queryset), 200, nothing created |
| Document upload fails after Release minted | whole atomic rolls back → no orphan Release, no EC (same guarantee as RF08 spec) |
| GET renders dropdown | open Releases in order + `+ Kria Release Foun` last; value `__new__` |

## Testing strategy (TDD — red first, django-tdd-loop skill)

In `apps/backlog/tests/` (`pytestmark = pytest.mark.django_db`):

1. `test_new_option_creates_next_release` — seed `TT_ON_<year>-003`,
   POST with `release="__new__"` → 302, `EC.release.release_code ==
   "TT_ON_<year>-004"`, old Releases' EC counts unchanged.
2. `test_new_option_when_year_empty_starts_at_001` — no Releases →
   new code ends with `-001`.
3. `test_new_option_despite_room_in_old_releases` — open 001 at 2/10,
   POST `__new__` → EC goes to 004, not 001 (the user's core demand).
4. `test_garbage_release_is_rejected` — POST `release="999999"` → 200,
   form errors, 0 ECs, 0 new Releases.
5. `test_service_retries_on_race` — service-level: pre-create the `n`
   row mid-flight (monkeypatch `Release.objects.create` to raise
   `IntegrityError` once) → service still returns `n+1`, one Release.
6. Existing `TestNewECForm` (direct-PK posts) must stay green unchanged.

## Commands

```bash
uv run pytest apps/backlog/tests/test_services.py apps/backlog/tests/test_views.py -q   # red → green
uv run pytest apps/backlog apps/workflow -q    # suite stays green (5 known dashboard/sidebar fails pre-exist)
uv run ruff check apps/backlog/ && uv run ruff format --check apps/backlog/forms.py apps/backlog/services.py
uv run python manage.py makemigrations --check --dry-run   # must report "no changes"
```

## Success criteria

- [x] All new tests green (8: 4 service + 4 view); existing form tests untouched and green.
- [x] Manual: Nova Solicitação dropdown shows open Releases + `+ Kria Release Foun` last; picking it creates `TT_ON_<year>-<next>` and lands the EC there. (covered by view tests)
- [x] Manual: with 001 half-empty, the new EC still goes to the fresh Release. (test_new_option_despite_room_in_old_releases)
- [x] No migration generated (`makemigrations --check`: no changes); ruff clean; no ARCHITECTURE §5 change needed.
