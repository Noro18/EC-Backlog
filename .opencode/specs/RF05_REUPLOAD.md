# Spec: RF05 Re-upload (new version) + resubmit to CD

## Goal
Let the requester attach a new document to a REJECTED EC, recorded as the next
`DocumentVersion` (v1.1, v1.2…), flipping the EC back to `in_validation` and
re-notifying the CD. This closes the rejection loop opened by chunk 2.

## SRD traceability
- **RF05** — version control: every upload auto-numbers (v1.0, v1.1, v2.0),
  all versions kept with `uploaded_at`, `uploaded_by`, `change_reason`.
- **RF07 (tail)** — optional CD reassignment at resubmit.
- **RF08 (reuse)** — the CD is notified of the new version (same mailer).
- Flow position: SRD § 6 step 7 (requester corrects and resubmits).
  Precondition: EC is `rejected` with at least one version + one review.

## Architecture & affected components
- EXTEND `apps/documents/services.py` — `create_next_version(ec, file,
  uploaded_by, change_reason, major=False)`. Row creation stays in `documents`
  (it owns `DocumentVersion`); numbering logic lives here, next to
  `create_first_version`.
- NEW `apps/workflow/services.py::resubmit_ec(...)` — the orchestrator.
  Status changes may ONLY happen via `workflow` services, so the flip
  `rejected → in_validation` lives here. It calls into `documents`
  (workflow → documents: downward, allowed), then queues the CD mail.
- NEW `apps/workflow/forms.py::ResubmitForm` — file + `change_reason`
  (required) + `major_change` tickbox + optional `responsible_cd` reassign.
- NEW `apps/workflow/views.py::ResubmitECView` + `templates/workflow/resubmit_ec.html`.
- EXTEND `apps/workflow/urls.py` (`resubmit_ec/<int:pk>/`, pk = EC id).
- EXTEND `templates/backlog/ec_detail.html` — "Resubmit" button, visible only
  to the EC's requester while `rejected`.
- No changes to `backlog` code. No model changes (verify with
  `makemigrations --check`).

## Database schema changes
**None.** `DocumentVersion` already stores `version_number`, `change_reason`,
`uploaded_at`, `uploaded_by`. Old `Review` rows stay attached to the version
they judged — history is never rewritten.

## Numbering contract
`create_next_version` reads the latest version string `v{major}.{minor}`:
- default: minor bump → v1.0 → v1.1 → v1.2…
- `major=True`: major bump → v1.2 → v2.0 (minor resets to 0).
- Unparseable latest (imported history edge): raise `ValidationError`.
- `change_reason` blank (after `strip()`) → `ValidationError` (a version
  without a reason is unauditable — RNF02 spirit).
- Runs `full_clean()` before save (extension/size validators fire here,
  same as `create_first_version`).

## Service contract
```python
resubmit_ec(ec, user, file, change_reason, major=False, responsible_cd=None) -> DocumentVersion
```
Guards (`ValidationError` / `PermissionDenied`):
1. `ec.status == REJECTED`, else `ValidationError` (nothing to resubmit).
2. `user == ec.requester`, else `PermissionDenied` (only the owner resubmits).
3. `responsible_cd`, if given, must be a CD-role user, else `ValidationError`.
Inside `transaction.atomic()`: `create_next_version(...)`, optional CD swap,
`status = IN_VALIDATION`, `queue_cd_assigned(ec)` (same RF08 mailer — the CD
learns of the new version through the mail they already know).

## View / form / URL
- `ResubmitECView(LoginRequiredMixin, UserPassesTestMixin, FormView)`:
  `test_func` = requester + `rejected`; `form_valid` calls `resubmit_ec`,
  surfaces `ValidationError` via `form.add_error`, redirects to `ec_detail`.
  File comes from `request.FILES` (form needs `enctype="multipart/form-data"` —
  same lesson as creation).
- Reassign field: dropdown of CD users, initial = current CD, optional.
- Template reuses `ec_form.html` styling; shows the rejection comment for
  context (what must be fixed) — read-only, from the latest review.

## Edge cases
| Case | Handling |
|---|---|
| Resubmit an `in_validation` / `approved` EC | status guard → `ValidationError` |
| Stranger (non-requester) POSTs | `PermissionDenied` (service) + gate (view) |
| Empty file / bad extension / oversize | `full_clean()` in documents service → field error |
| Blank `change_reason` | `ValidationError` before any write |
| Double-submit (two tabs) | 2nd call fails the status guard (now `in_validation`) |
| CD deleted/deactivated meanwhile | reassignment at resubmit is the remedy (RF07 tail) |

## Tests (TDD, extend `apps/workflow/tests/test_review.py` + documents tests)
1. Numbering: v1.0 → v1.1; `major=True` → v2.0 (documents service level).
2. Blank `change_reason` → `ValidationError`, no row, status unchanged.
3. Non-requester resubmit → `PermissionDenied`, status unchanged.
4. Happy path: new version row + status `in_validation` + old review still on v1.0.
5. CD mail queued on resubmit (outbox, `captureOnCommitCallbacks` + `sync`).
6. View: requester GET 200, stranger GET 403, POST resubmits (302).

## Out of scope
- DES routing / `close_ec` (chunk 4, RF11).
- Editing or deleting old versions or reviews — immutable history.
- Requester editing reference/description at resubmit — new file only.

## Decisions (confirm before coding)
1. **Major bump:** uploader tickbox `major_change` (recommended) vs minor-only
   always — when SHOULD a v2.0 ever happen?
2. **Reassignment:** allow swapping CD at resubmit (recommended, RF07 tail)
   vs same-CD-only.
3. **`change_reason`:** required (recommended) vs optional.

## Verification
- [x] `uv run pytest -q` — full chunk green (3 numbering, 4 resubmit service,
  3 resubmit view; only failures are the 4 pre-existing PR #44 ones, issue #46)
- [x] `uv run ruff check .` and `uv run python manage.py check` clean
- [x] `makemigrations --check --dry-run` → "No changes detected" (no models added)
- [x] Manual: requester resubmits on a rejected EC; EC returns to `in_validation`;
  CD mailed; timeline keeps v1.0 + review

## Status
- [x] SPEC_APPROVED — approved 2026-10-13; decisions: major tickbox, reassignment allowed, change_reason required
