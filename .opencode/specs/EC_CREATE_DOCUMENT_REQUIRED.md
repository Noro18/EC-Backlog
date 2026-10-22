# Spec: Document is mandatory when creating an EC

**Status:** approved (`SPEC_APPROVED`, 2026-10-22) — amends `EC_CREATE.md` Assumption 6.

## Objective

A new EC must not exist without its specification document. Today
`ECCreateForm.document` is `required=False`, so a requester can click **Criar EC** with an
empty file input and get a real EC row with zero `DocumentVersion` rows.

- As a requester who forgot the file, I click **Criar EC** and get a red error on the
  document field — **no EC is created**, no EC number is consumed, no release seat is taken,
  no CD email is queued.
- As a requester who attached the file, nothing changes: EC + `DocumentVersion` `v1.0` +
  success message.

**Why this exists — SRD mapping.** RF06 (upload of the specification document) read together
with RF07 ("**After the document is uploaded**, the system must present the option to assign
to a CD") and SRD § 6 step 4 (upload precedes assignment). The current optional behaviour
contradicts that to-be flow.

**Supersedes:** `EC_CREATE.md` Assumption 6 ("The document field is optional") and its
Success Criteria line ("An optional upload lands as `DocumentVersion` `v1.0`; the rest of the
form works with no file").

## Architecture / affected components

| Component | Change |
|---|---|
| `apps/backlog/forms.py` | `ECCreateForm.document` → `required=True` (the only behavioural change) |
| `templates/backlog/ec_form.html` | document label gets the `<span class="text-danger">*</span>` marker, like the other required fields (cosmetic, RNF05) |
| `apps/backlog/views.py` | **no change** — `if file := self.request.FILES.get("document")` stays as a defensive guard; with `required=True` it is always truthy when `form_valid` runs |
| `apps/backlog/services.py` | **no change** — `create_ec()` never handled documents |
| `apps/documents/*` | **no change** — validators/`create_first_version` already run on the file |

Enforcement lives in the **form**, not the view or service: `ECCreateForm` validates before
`NewECView.form_valid` is ever called, so the transaction at `views.py:99` never opens and
nothing is written (EC_CREATE.md Decision 1: "validation lives here, saving lives in the
service").

## Database schema changes

**None.** No model edit, no migration. `DocumentVersion` already exists; historical/imported
ECs (`is_imported=True`) may legitimately have no documents — this rule applies only to ECs
created through `/backlog/new_ec/`.

## Input / output payloads and edge cases

POST `/backlog/new_ec/` — all existing fields unchanged; `document` (file, `.docx`/`.pdf`)
becomes mandatory.

| Case | Expected outcome |
|---|---|
| Valid payload, **no file** | `200`, form re-rendered, `"document" in form.errors` ("This field is required."), `EC.objects.count() == 0`, no `LogEntry`, `mail.outbox == []`, next valid POST still mints `-001` |
| Valid payload + `.docx` | `302`, EC + `DocumentVersion` `v1.0` (unchanged) |
| Valid payload + `.exe` / `.txt` | `200`, error on `document`, **no EC** (unchanged — validators in `documents`) |
| Missing file **and** invalid release | `200`, errors on **both** fields (form errors are collected field-by-field) |
| Missing file **and** role CD | `403` — the role gate (`UserPassesTestMixin`) still runs before any form validation (unchanged) |
| Empty file (0 bytes) | rejected by the documents validators, no EC (rollback path already covered) |

Race conditions: none — the rule is enforced before any DB write begins.

## Tests (TDD — red first, per `django-tdd-loop`)

**New tests**

1. `POST` valid payload **without** `document` → `200`, `"document" in form.errors`,
   `EC.objects.count() == 0`, `DocumentVersion.objects.count() == 0`.
2. Same POST, then a valid POST **with** a file → the EC minted is `<year>-001` (the failed
   attempt consumed no number).
3. `GET` the form → `form.fields["document"].required is True` and the rendered label shows
   the `*` marker.

**Existing tests that must gain a file** (they POST a "valid" form today — they are the
proof that the old optional rule was load-bearing):

| File | Test |
|---|---|
| `apps/backlog/tests/test_views.py:362` | `test_administrator_gets_and_creates` |
| `apps/backlog/tests/test_views.py:416` | `test_valid_post_creates_ec_and_renders_message` |
| `apps/backlog/tests/test_views.py:442` | `test_blank_description_is_rejected` (add file so only `description` fails) |
| `apps/backlog/tests/test_views.py:460` | `test_post_to_full_release_is_refused` (add file so the capacity path is the one exercised) |
| `apps/backlog/tests/test_views.py:478` | `test_two_consecutive_posts_increment_the_number` |
| `apps/backlog/tests/test_views.py:607,629,653` | `TestReleaseOnDemand` — the three on-demand-create POSTs |
| `apps/backlog/tests/test_views.py:674` | `test_garbage_release_is_rejected` (add file so only `release` fails) |
| `apps/backlog/tests/test_views.py:711` | `test_post_full_reference_creates_ec` |
| `apps/backlog/tests/test_auditlog.py:16` | `test_creating_an_ec_records_the_actor` |
| `apps/workflow/tests/test_notifications.py` | the two `302` EC-create POSTs (the `.txt` rollback test already uploads and stays as is) |

**Deliberately untouched:** the CD `403` POST (`data={}`), `test_exe_upload_is_rejected`,
all service tests (`create_ec()` has no document parameter), `test_dashboard.py`
`test_ec_without_a_document_counts_as_in_validation` (that EC is factory-made, not
form-made).

## Commands

```bash
uv run pytest apps/backlog/tests/ apps/workflow/tests/ -q
uv run pytest
uv run ruff check . && uv run ruff format apps/backlog/
```

## Boundaries

- **Always:** TDD (the three new tests fail before the one-line change), form-level
  validation only, no migration.
- **Ask first:** moving the rule into a service/model constraint, touching `documents` or
  `workflow` code, changing `EC_CREATE.md` itself (this file proposes the amendment; the
  parent spec is edited only after approval).
- **Never:** put the check in `form_valid` after `create_ec()` (it would have to roll back a
  minted number), remove the `if file :=` guard in the view, make the field required only in
  the HTML (`required` attribute is a client-side courtesy, not the gate).

## Success Criteria

- Submitting the form without a file creates **nothing** and shows a field error.
- The first successful creation after a failed attempt is still `<year>-001`.
- Full suite green (existing tests updated only by adding a file to their payload), ruff
  clean.
- `EC_CREATE.md` Assumption 6 and its Success Criteria line updated to match.

## Open Questions

None — behaviour confirmed with the user 2026-10-22: "EC tidak boleh terbentuk sama sekali
kalau dokumen belum di-upload."
