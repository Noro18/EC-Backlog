# Spec: RF09 CD Decision (approve / reject) + RF10 requester notification

## Goal
Let the assigned CD approve or reject an EC that is `in_validation`, recording the
decision as a `Review` on the latest `DocumentVersion`, flipping `ec.status`, and
emailing the requester the outcome (RF10). This is the heart of the workflow —
chunks 3 (re-upload) and 4 (DES routing) both hang off the statuses set here.

## SRD traceability
- **RF09** — approve/reject with comment (comment mandatory on rejection).
- **RF10** — notify the requester on a delay/reject decision **with the reason**.
- **RF04/RF11** — NOT this chunk (DES routing + go-live come later).
- Flow position: SRD § 6 step 6 (CD validates). Precondition: EC is `in_validation`
  with exactly one unreviewed latest version (guaranteed today: creation makes v1.0
  and no re-upload exists yet — chunk 3).

## Architecture & affected components
- NEW `apps/workflow/services.py` — `approve_ec(ec, cd)`, `reject_ec(ec, cd, comment)`.
  Only these functions may flip `in_validation → approved / rejected`
  (ARCHITECTURE: status changes only via `workflow` services).
- NEW `apps/workflow/selectors.py` — `latest_version(ec)` (thin read helper).
- EXTEND `apps/workflow/notifications.py` — `queue_decision_made(ec)` +
  `send_decision_email(ec_id)`, mirroring the RF08 pair.
- NEW `apps/workflow/forms.py` — `ReviewForm` (decision radio + comment).
- NEW `apps/workflow/views.py::ReviewECView` + `templates/workflow/review_ec.html`.
- NEW `apps/workflow/urls.py` (`review_ec/<int:pk>/`, pk = EC id), included in
  `config/urls.py` under `workflow/`.
- EXTEND `templates/backlog/ec_detail.html` — "Review" button, visible only to the
  assigned CD while `in_validation`.
- Reads `documents.DocumentVersion` via `ec.versions` (workflow → documents:
  downward, always allowed). No changes to `backlog` or `documents` code.

## Database schema changes
**None.** `workflow_review` already has everything this chunk needs:
- `OneToOneField` to `DocumentVersion` → one decision per version (a second
  decision on the same version fails at the DB level).
- `CheckConstraint review_rejection_requires_comment` → rejection without comment
  fails at the DB level even if app validation is bypassed.
- Verify with `uv run python manage.py makemigrations --check --dry-run` (must
  output "No changes detected").

## Service contracts
```python
approve_ec(ec: EC, cd: User) -> Review
reject_ec(ec: EC, cd: User, comment: str) -> Review
```
Shared guards (raise `django.core.exceptions.ValidationError` / `PermissionDenied`):
1. `ec.status == IN_VALIDATION`, else `ValidationError` (double-submit / stale tab).
2. `cd == ec.responsible_cd`, else `PermissionDenied` (only the assigned CD decides).
3. Latest version `ec.versions.order_by("-uploaded_at").first()` must exist and
   have no `review` yet, else `ValidationError`.
`approve_ec`: create `Review(decision=approved, comment="")`, set
`status = APPROVED`.
`reject_ec`: blank comment (after `strip()`) → `ValidationError`; create
`Review(decision=rejected, comment=…)`, set `status = REJECTED`.
Both run inside `transaction.atomic()` and call `queue_decision_made(ec)` **inside**
the atomic block — same parcel pattern as RF08, so a rollback discards the email.

## Notification contract (RF10)
`queue_decision_made(ec)` → `on_commit(async_task(send_decision_email, ec.pk))`.
`send_decision_email(ec_id)` re-fetches with `select_related("requester")`,
guards (`DoesNotExist` → return, no requester email → return), never raises.
- Subject: `EC {ec_code}: aprovada` / `EC {ec_code}: rejeitada`.
- Body: decision, EC code + reference, CD name, detail link via `SITE_URL`
  (same pattern as RF08). **On rejection the CD's comment is included verbatim** —
  that is the RF10 "with the reason" requirement.
- Test settings reuse `sync: True` + locmem (no new settings needed).

## View / form / URL
- `ReviewForm(forms.Form)`: `decision = ChoiceField(radio: approve/reject)`,
  `comment = CharField(Textarea, required=False)`; `clean()` requires a non-blank
  comment when `decision == rejected` (form-level mirror of the DB constraint).
- `ReviewECView(LoginRequiredMixin, UserPassesTestMixin, FormView)`:
  `test_func` = request.user is the EC's `responsible_cd` **and** EC is
  `in_validation`; on valid form calls the matching service, redirects to
  `backlog:ec_detail`. Service `ValidationError` (race: status changed between
  GET and POST) surfaces via `form.add_error(None, …)`, never a 500.
- Template reuses `ec_form.html` styling; shows EC code + reference + latest
  version number as context so the CD knows what they are deciding on.

## Edge cases
| Case | Handling |
|---|---|
| Double-click / stale tab double POST | 2nd call fails the status guard; user sees a form error |
| Reject with whitespace-only comment | `strip()` → `ValidationError` (form + service + DB triple cover) |
| Worker runs after EC deleted | `DoesNotExist` → silent return (RF08 pattern) |
| Requester without email | skip send, decision still recorded |
| CD tries to decide someone else's EC | `PermissionDenied` (service) + gate (view) — double cover |
| Non-latest version reviewed | impossible by construction: service always targets latest |

## Tests (TDD, `apps/workflow/tests/test_review.py`, `pytestmark = django_db`)
1. `approve_ec` creates an approved `Review` on the latest version + flips status.
2. `reject_ec` with comment stores the comment verbatim + flips status.
3. `reject_ec` with blank comment raises `ValidationError`, status unchanged,
   no `Review` row (use `captureOnCommitCallbacks(execute=True)` + `sync: True`
   so the requester email must also be absent).
4. Second decision on the same EC raises `ValidationError` (status guard).
5. Decision by a CD other than `responsible_cd` raises `PermissionDenied`,
   status unchanged (service guard + view gate double cover).
5. Requester email queued on decision; rejection body contains the CD's comment
   and the detail link (locmem outbox, `sync: True`).

## Out of scope (later chunks / issues)
- DES routing + `close_ec` (chunk 4, RF11) — APPROVED ECs simply wait.
- Re-upload + `create_next_version` (chunk 3, RF05/#34) — REJECTED ECs wait.
- Reassigning the CD after rejection (chunk 3, RF07 tail).
- Admin override of a decision — **not provided**; open question, do not invent.
- Editing a `Review` after the fact — decisions are final (matches audit
  immutability, RNF02).

## Decisions (confirm before coding)
1. **Who may decide:** assigned CD only (recommended) — no admin override.
   If the CD is unavailable, reassignment (chunk 3) is the remedy.
2. **Decision input:** one form with approve/reject radio (recommended) vs two
   separate buttons/URLs — one form keeps validation in one place.
3. **Email language:** PT, same tone as the RF08 mail (recommended).

## Verification
- [x] `uv run pytest -q` — 152 passed incl. 15 new RF09 tests (2 selector, 5 service,
  2 email integration, 4 mailer guards, 3 view); only failures are the 4 pre-existing
  PR #44 ones (issue #46), untouched by this chunk
- [x] `uv run ruff check .` and `uv run python manage.py check` clean
- [x] `makemigrations --check --dry-run` → "No changes detected" (no models added)
- [x] Manual: CD sees Review button on an `in_validation` EC, approves + rejects
  with comment; requester mails verified via worker in RF08 pattern

## Status
- [x] SPEC_APPROVED — approved 2026-10-12; decisions: assigned-CD-only, one radio form, PT email
