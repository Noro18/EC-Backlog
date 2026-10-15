# Spec: RF11 Route approved EC to DES (requester) + RF04 go-live date

## Goal
After CD approval, the REQUESTER sends the EC to DES. Routing closes the EC
automatically; when the last open EC of a Release closes, the Release closes
too. DES gets mailed. Later, the requester records the go-live date on the
closed Release in a separate manual action. The CD's role ends at approval.
DES has no action in the system.

## SRD traceability
- **RF11** — "once approved, the requester must be able to route the
  specification … to the DES team"; routing auto-closes the EC, and the
  Release closes with its last EC.
- **RF04** — go-live date recorded manually by the requester on the closed
  Release (SRD § 6 step 12), NOT at routing time.
- **NOT this chunk:** `close_ec` as a standalone action / Cancelled flows.

## Architecture & affected components
- EXTEND `apps/workflow/services.py` — `route_to_des(ec, user)`: guards, flip
  EC to CLOSED, auto-close the Release when its last EC closes, queue DES mail.
- NEW `apps/backlog/services.py::record_go_live(release, user, go_live_date)`:
  the date lives on `Release`, so its writer lives in `backlog`. Guards: release
  closed (`is_open=False`), caller has the requester role, real date.
- EXTEND `apps/workflow/notifications.py` — `queue_des_routed(ec)` +
  `send_des_routed_email(ec_id)` (parcel pattern as RF08/RF10).
- `apps/workflow/views.py::RouteToDESView` — POST-only (no `get()` → GET 405).
- NEW `apps/backlog/views.py` go-live view (POST-only) + URL + date form on the
  release detail page, visible to requesters only while the release is closed.
- EXTEND `templates/backlog/ec_detail.html` — "Send to DES" button + Yes/No
  modal (no date input); visible only to the EC's requester while `approved`.
- No changes to `documents` / `accounts` code.

## Database schema changes
**None.** Uses `EC.status`, `Release.is_open`, `Release.production_go_live_date`.
Verify with `makemigrations --check --dry-run`.

## Service contracts
```python
route_to_des(ec: EC, user) -> EC
```
Guards (`ValidationError` / `PermissionDenied`):
1. `ec.status == APPROVED`, else `ValidationError`.
2. `user.pk == ec.requester_id`, else `PermissionDenied` — only the owning
   requester routes. The CD (even the approver) cannot.
Inside `transaction.atomic()`: `status = CLOSED` + save; if no EC of this
Release remains outside `closed`/`cancelled`, set `is_open = False` + save;
`queue_des_routed(ec)`; return ec.

```python
record_go_live(release, user, go_live_date: date) -> Release  # backlog/services.py
```
Guards: `release.is_open is False`, else `ValidationError` (date entry opens
only after closure); `user.role == REQUESTER`, else `PermissionDenied`;
`go_live_date` real date, else `ValidationError`. Sets the field + save.
Overwriting an existing date is allowed (corrections happen); auditlog records it.

## Notification contract
`queue_des_routed(ec)` → `on_commit(async_task(send_des_routed_email, ec.pk))`.
Recipients: all DES_TEAM users with an email. Empty set → silent return;
`DoesNotExist` → return; never raises. Subject `EC {ec_code}: enviada ao DES`;
body: EC code, reference, description, approving CD, routing requester,
SITE_URL detail link. (No go-live line — the date doesn't exist yet at routing.)

## View / URL
- `RouteToDESView` as before (requester + `approved` gate, messages + redirect,
  GET 405). Modal: question + No/Yes only.
- Go-live view (backlog): POST-only, requester role + closed-release gate,
  parses ISO date, success/error messages, redirects to `release_detail`.
  Release detail shows the date form (required `<input type="date">`) only to
  requesters while closed; otherwise the stored date (or "—").

## Edge cases
| Case | Handling |
|---|---|
| Double-click route | 2nd POST fails the status guard → error message, never 500 |
| CD crafts the route POST | `PermissionDenied` |
| Route with siblings still open | EC closes, Release stays open |
| Go-live on an open Release | `ValidationError` — option appears only after closure |
| No DES user with email | routing succeeds; mail silently skipped |

## Tests
`apps/workflow/tests/test_des_routing.py`:
1. Happy path: requester → `closed`, no new version/review rows.
2. Last-EC routing closes the Release; sibling-open routing leaves it open.
3. Wrong status → `ValidationError`; CD/stranger → `PermissionDenied`.
4. DES mail queued.
5. View: stranger/CD POST 403; requester POST → 302 + closed; GET → 405.
New `apps/backlog/tests/test_go_live.py`:
6. Requester sets date on closed release → saved.
7. Open release / non-requester / bad date → refused, date untouched.

## Out of scope
- Standalone `close_ec` / Cancelled transitions.
- DES-side actions — DES reads + downloads only (media auth stays issue #37).

## Decisions (decided by user)
1. Router is the requester; CD ends at approval; DES reads only.
2. Routing closes the EC; Release closes with its last EC.
3. Go-live is manual, later, on the closed Release — never automatic at routing.

## Verification
- [x] `uv run pytest -q` — **200 passed, 0 failed**: full suite green (12 routing
  + 7 go-live tests)
- [x] `uv run ruff check .` and `uv run python manage.py check` clean
- [x] `makemigrations --check --dry-run` → "No changes detected"
- [x] Manual: requester routes last EC → release closes → date button appears →
  date saved; DES mailed at routing

## Status
- [x] SPEC_APPROVED — corrected flow confirmed by user
