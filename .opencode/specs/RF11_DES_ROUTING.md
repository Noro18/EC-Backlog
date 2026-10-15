# Spec: RF11 Routing to DES (approved → sent_to_des)

## Goal
Let an approved EC be routed to the DES team through the system, flipping
`ec.status` from `approved` to `sent_to_des` with full history/traceability.
This is chunk 4 — APPROVED ECs currently wait with no way forward.

## SRD traceability
- **RF11** — once approved, the team routes the specification to the DES team
  through the same system, preserving history and traceability.
- **RF04 / close / cancel** — NOT this chunk (go-live date + Closed/Cancelled
  transitions come later).
- Flow position: SRD § 6 step 9 (route after approval). Precondition: EC is
  `approved` (set only by `approve_ec`, RF09).
- DES team visibility already exists: `ECListView` + selector filter
  `status=SENT_TO_DES` (`apps/backlog/selectors.py:72`), and the detail page.

## Architecture & affected components
- EXTEND `apps/workflow/services.py` — `route_to_des(ec, user)`. Only this
  function may flip `approved → sent_to_des` (ARCHITECTURE: status changes
  only via `workflow` services).
- NEW `apps/workflow/views.py::RouteToDESView` + `templates/workflow/route_to_des.html`
  (confirm page mirroring `review_ec.html` styling).
- EXTEND `apps/workflow/urls.py` (`route_to_des/<int:pk>/`, pk = EC id).
- EXTEND `templates/backlog/ec_detail.html` — "Route to DES" button, visible
  only while `approved` and only to the routing-authorized user (see Decision 1).
- No changes to `backlog` or `documents` code. Audit (RNF02) is automatic:
  `EC` is already registered with django-auditlog, so the status flip is
  recorded with user + timestamp.

## Database schema changes
**None.** `EC.status` already includes `sent_to_des`; no new field, no new
model. Verify with `uv run python manage.py makemigrations --check --dry-run`
(must output "No changes detected").

## Service contract
```python
route_to_des(ec: EC, user: User) -> EC
```
Guards (raise `django.core.exceptions.ValidationError` / `PermissionDenied`):
1. `ec.status == APPROVED`, else `ValidationError` (double-submit / stale tab —
   same race pattern as `ReviewECView`).
2. `user.pk == ec.responsible_cd_id` (**agreed 2026-10-14: the approving CD
   routes** — the CD who approved forwards to DES), else `PermissionDenied`.
Body: inside `transaction.atomic()`, set `status = SENT_TO_DES` via
`ec.save(update_fields=["status"])`. No `Review` row, no new document version —
routing is a pure status transition on the already-approved version.

## Input / output
- Input: EC pk from URL; POST with empty body (confirm button) + CSRF.
- Output: redirect to `backlog:ec_detail`; success message
  `EC {ec_code} enviada para a equipa DES.` (PT, matching existing messages).
- Service `ValidationError` (race: status changed between GET and POST)
  surfaces via `form.add_error(None, …)` / messages, never a 500.

## Notification contract
**Email to the DES team (agreed 2026-10-14).** `queue_routed_to_des(ec)` →
`on_commit(async_task(send_des_routed_email, ec.pk))`, mirroring the RF08/RF10
pairs. `send_des_routed_email(ec_id)` re-fetches the EC, collects recipients =
all `User` with `role=des_team` and a non-empty email, guards
(`DoesNotExist` → return, no recipients → return), never raises. Subject/body
in PT, same tone as RF08/RF10 mails: EC code + reference + release +
approving-CD name + detail link via `SITE_URL`. Called **inside** the
`route_to_des` atomic block so a rollback discards the email.

## View / URL
- `RouteToDESView(LoginRequiredMixin, UserPassesTestMixin, FormView)` with a
  minimal confirm form (no fields — or a single confirm checkbox; see
  Decision 3). `test_func` = EC is `approved` **and** request.user is the
  authorized router. `dispatch` loads the EC via `get_object_or_404`
  (same as `ReviewECView` / `ResubmitECView`).
- Template shows EC code + reference + release + approved version number so
  the user confirms the right EC.

## Edge cases
| Case | Handling |
|---|---|
| Double-click / stale tab double POST | 2nd call fails the status guard; user sees a form error |
| Non-approved EC posted directly (crafted POST) | `ValidationError` (service) + gate (view) — double cover |
| Someone else's EC routed by another user | `PermissionDenied` (service) + gate (view) — double cover |
| Rejected / in_validation EC | unreachable: button hidden + guards reject |
| `sent_to_des` EC routed again | status guard rejects (`approved` required) |
| Routing an imported historical EC | same guards apply; imported rows have no requester → `PermissionDenied` for everyone (no crash) |

## Tests (TDD, `apps/workflow/tests/test_route_to_des.py`, `pytestmark = django_db`)
1. `route_to_des` on an approved EC flips status to `sent_to_des`, no new
   `Review` / version rows; DES email queued (locmem outbox, `sync: True`).
2. `route_to_des` on a non-approved EC raises `ValidationError`, status unchanged.
3. `route_to_des` by anyone other than the assigned CD raises `PermissionDenied`,
   status unchanged, no email queued.
4. View: assigned CD GET sees the confirm page; POST routes + redirects
   to `ec_detail`.
5. View: unauthorized user GET/POST → 403 (gate); crafted POST on approved EC
   by outsider → no status change.

## Out of scope (later chunks / issues)
- RF04 go-live date entry — stays manual on the Release, separate chunk.
- `close_ec` / `cancel_ec` (Closed/Cancelled) — SRD § 6 step 13, separate chunk.
- DES-side actions (accept / implement) — SRD marks DDS implementation out of scope.
- Admin override of routing — **not provided**; open question, do not invent.
- DES email notification — only if Decision 2 says so (separate chunk either way).

## Decisions (agreed 2026-10-14)
1. **Who may route:** the approving CD (`responsible_cd` at approval time).
2. **DES notification:** django-q2 email to all users with `role=des_team`.
3. **Confirm UI:** dedicated confirm page (no objection raised; mirrors
   review/resubmit pattern).

## Verification
- [x] `uv run pytest -q` — 191 passed incl. 9 new RF11 tests (4 service, 1 email,
  4 view); full suite green
- [x] `uv run ruff check .` and `uv run python manage.py check` clean
- [x] `makemigrations --check --dry-run` → "No changes detected" (no models added)
- [ ] Manual: CD sees Enviar-para-DES button on an `approved` EC, confirms,
  status becomes Sent to DES; DES-team users receive the email

## Status
- [x] SPEC_APPROVED — approved 2026-10-14 (lowercase "spec_approved" accepted);
  decisions: approving-CD routes, email to all des_team users, confirm page
- [x] Implemented on branch `feat/rf11-des-routing` (TDD: red → green, 9 tests)
