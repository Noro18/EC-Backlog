# Spec: RF08 — Email notification on CD assignment

## Objective

When an EC is created, the responsible CD automatically receives an email telling them
that validation is needed (**RF08**), sent through django-q2 so a slow or failing mail
server never blocks the requester's submission (**RNF03**).

- As a requester, I submit an EC with a CD chosen and the system notifies that CD by
  email without me doing anything extra.
- As a CD, I receive an email identifying the EC (code, reference, description, who
  requested it) with a clickable link to its detail page.
- As a requester whose submission fails validation, I trigger **no** email at all —
  a rolled-back transaction must never notify anyone.

**Out of scope:** admin alert on final task failure (RNF03 follow-up, separate slice),
reassignment after rejection (chunk 3 — reuses `queue_cd_assigned` unchanged), the RF10
decision email (chunk 2), any notification table.

## Assumptions

1. **Assignment happens at creation** (EC_CREATE Decision 3): the create form's
   `responsible_cd` field is `required=True`, so *every* EC creation is an assignment
   and every successful creation notifies exactly one CD. This is the first of two
   trigger points; the second (re-upload after rejection) arrives in chunk 3.
2. `config/settings/test.py` already sets `Q_CLUSTER = {**Q_CLUSTER, "sync": True}` and
   the locmem email backend — in tests `async_task` runs **synchronously in-process**,
   so asserting `mail.outbox` after `captureOnCommitCallbacks` is a true end-to-end
   check, no mocking needed. (Django 6.1 API: `TestCase.captureOnCommitCallbacks` —
   a classmethod on `django.test.TestCase`, not an import from `django.test.utils`.)
3. Dev prints emails to the console (`config/settings/local.py`);
   production parses `EMAIL_URL` (`config/settings/production.py`). Nothing to change.
4. `User.email` is `unique=True`, but legacy/admin-created accounts may hold an empty
   address — the task guards rather than crashing the worker.

## Decisions (agreed 2026-10-08)

1. **Documented import exception (Option A).** `NewECView.form_valid` (in `backlog`)
   calls `queue_cd_assigned` from `apps.workflow.notifications` — an *upward* import
   (`backlog → workflow` is forbidden by ARCHITECTURE §5). Same precedent as Decision 2
   (`backlog → documents` for `create_first_version`): the rule is not broken silently,
   it is widened with a new entry in ARCHITECTURE §5 naming this exact call site.
   Rejected alternatives: signal in `workflow/apps.py` (implicit, untraceable), splitting
   assignment out of creation (reworks the create form, contradicts EC_CREATE Decision 3).
2. **Call registered *inside* the `atomic()` block**, immediately after `create_ec`
   returns. If `create_first_version` later raises, the savepoint rollback **discards
   the `on_commit` hook** — no email for a failed submission by construction, not by an
   `if`. This is what makes test 3 pass without extra error handling.
3. **The task takes a primitive `ec_id`, never a model instance** — queue payloads must
   be picklable and must re-read the DB *inside* the worker (state may have changed
   between enqueue and execution).
4. **Email carries an absolute link (Option 2).** New setting
   `SITE_URL = env("SITE_URL", default="http://localhost:8000")` in `base.py`, documented
   in `.env.example`. The task builds
   `f"{settings.SITE_URL.rstrip('/')}{reverse('backlog:ec_detail', args=[ec.pk])}"`.
   Production **must** set `SITE_URL` in `.env`; the default only points at localhost.
   `reverse()` works outside a request — no site framework, no request object needed.
5. **RNF03 retries come free** from the existing `Q_CLUSTER` (`retry: 120`,
   `max_attempts: 3`). The admin alert on final failure needs a settings `error` hook
   and is explicitly **deferred** — retry alone is already "a retry mechanism" for this
   slice.
6. **Sender:** `settings.DEFAULT_FROM_EMAIL` (Django's default in dev, overridable via
   env in production). No new setting.

## System architecture — affected components

```
apps/workflow/                       ← owns notifications (ARCHITECTURE:85)
├── notifications.py                 NEW — queue_cd_assigned(ec) + send_cd_assigned_email(ec_id)
└── tests/
    └── test_notifications.py        NEW — 5 tests (TDD, red first)

apps/backlog/
└── views.py                         +1 line in NewECView.form_valid (inside atomic)

config/settings/base.py              +SITE_URL = env("SITE_URL", default="http://localhost:8000")
.env.example                         +SITE_URL=http://localhost:8000
docs/ARCHITECTURE.md §5              +documented-exception entry (backlog → workflow, this call site)
```

**Database schema changes: none.** No models touched, no migrations. Emails are sent
tasks with no table (`database-scheme.md` §8: "There is **no** notification table").

## Code style — the two functions

```python
# apps/workflow/notifications.py
from django.db import transaction
from django_q.tasks import async_task

def queue_cd_assigned(ec) -> None:
    """RF08: after the creating transaction commits, enqueue the CD email.
    Registered inside the caller's atomic() so a rollback discards the hook."""
    transaction.on_commit(lambda: async_task(send_cd_assigned_email, ec.pk))

def send_cd_assigned_email(ec_id: int) -> None:
    """django-q2 task: re-fetch the EC, guard, send. Never raise."""
    # TODO (student): EC.DoesNotExist → return silently (deleted before the task ran)
    # TODO (student): empty responsible_cd.email → return silently
    # TODO (student): send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [cd.email])
```

- Subject (PT): `EC {ec.ec_code}: validação pendente`
- Body (PT): EC code, reference, description, requester's name, absolute detail link.
- Only the **view** gains one line:

```python
# apps/backlog/views.py — inside the with transaction.atomic(): block, after create_ec(...)
queue_cd_assigned(ec)   # RF08 — import from apps.workflow.notifications (ARCHITECTURE §5 exception)
```

## Payloads and edge cases

| Case | Expected behaviour |
|---|---|
| Successful create (POST form, all valid) | exactly 1 email, to `responsible_cd.email`, after commit |
| `create_first_version` raises (bad file type) | rollback discards the hook → **0 emails**, 0 EC rows, form re-rendered with the error |
| EC deleted between enqueue and execution | task returns silently — a worker crash would burn all 3 retries for nothing |
| `responsible_cd.email` empty | task returns silently (no send, no crash) |
| Task enqueued but worker down | django-q2 ORM broker keeps the row; retried per `Q_CLUSTER` (`max_attempts: 3`) |
| `SITE_URL` unset in production | link points at `http://localhost:8000` — deployment checklist item, not code |

## Testing strategy (TDD — write the red test first)

All in `apps/workflow/tests/test_notifications.py` (`pytestmark = pytest.mark.django_db`).
The create-form POST is the real trigger — the only path that runs a live request
through the middleware, the form, the service and the queue hook.

1. `test_create_ec_sends_email_to_the_cd` — POST `backlog:ec_form` inside
   `captureOnCommitCallbacks(execute=True)` → `len(mail.outbox) == 1`,
   recipient == CD's email, subject contains `ec.ec_code`.
2. `test_email_body_carries_reference_requester_and_link` — body contains the
   `reference`, the requester's full name, and the absolute link
   (`settings.SITE_URL` + `/backlog/detail_ec/<pk>/`).
3. `test_rollback_sends_no_email` — POST with a `.txt` document (validators reject it)
   → response 200 with a form error, `mail.outbox` empty, `EC` count unchanged.
4. `test_task_ignores_a_deleted_ec` — call `send_cd_assigned_email(<missing pk>)`
   directly → no exception, `mail.outbox` empty.
5. `test_task_skips_a_cd_without_email` — CD with `email=""`, call the task directly
   → no send, no crash.

## Commands

```bash
uv run pytest apps/workflow/tests/test_notifications.py -q   # red → green
uv run pytest                                                # full suite (135+) must stay green
uv run ruff check . && uv run ruff format apps/workflow/
uv run python manage.py runserver                            # manual: create an EC, watch the console backend print the email
```

## Success criteria

- [x] All 5 tests green; full suite green; ruff clean; `manage.py check` clean. (140 passed, 2026-10-08)
- [x] Manual: creating an EC in dev prints a Portuguese email to the console with a
      clickable `http://localhost:8000/backlog/detail_ec/<pk>/` link. (proven live: real `qcluster` worker processed a real ticket)
- [x] Manual: submitting the form with a `.txt` file prints **no** email. (test 3, same code path)
- [x] ARCHITECTURE §5 lists the new exception naming `NewECView.form_valid` explicitly.
- [x] Issue #35 closed (PR #45 merged 2026-10-08).
