# Spec — Pending EC Validation Queue (`Solicitações Pendentes`)

## Objective

Provide a dedicated page listing ECs that are currently waiting for CD validation, replacing
the `#` placeholder behind `Solicitações Pendentes` in the role-based sidebar.

- A CD sees pending ECs assigned to that CD only.
- An Administrator sees all pending ECs, to support operational monitoring.
- Each row shows enough information to identify the EC and its latest submitted document, and
  provides a link to the existing EC detail/review flow.
- The page is read-only: approval, rejection, comments, and status changes continue through the
  existing workflow views and services.

This feature is derived from RF07 (assignment to a CD), RF09 (CD decision), RF12 (consultation),
RNF01 (role-based access), and RNF05 (usability). The SRD does not specify a separate pending-queue
page; this spec proposes it as a focused way to expose the existing validation work queue.

## Tech Stack

Django 6.1, `django-tables2`, existing `EC`, `DocumentVersion`, and `Review` models. **No new
dependency.**

## Commands

```bash
uv run pytest apps/backlog/tests/test_pending_ecs.py  # feature tests
uv run pytest                                         # full suite
uv run ruff check .                                   # lint
uv run python manage.py runserver                     # manual role-based check
```

## System Architecture

```
apps/backlog/
├── selectors.py   # add pending_ecs(user): select eligible ECs and latest document data
├── tables.py      # reuse/adapt CDPendingReviewTable for the full queue
├── views.py       # add PendingECListView with login and role checks
├── urls.py        # add /backlog/pending-ecs/ route
└── tests/
    └── test_pending_ecs.py  # NEW: visibility, row data, empty queue, ordering

templates/backlog/
└── pending_ecs.html  # NEW: Portuguese page title, table, empty state

templates/base.html  # EDIT: replace the pending-requests # link with the named route
```

The selector owns the filtering and latest-version selection. The view stays thin. Workflow
decisions remain owned by `workflow`; this page must not update `EC.status` or create a `Review`.
The existing `cd_dashboard()` queue is not removed or repurposed by this spec.

## Database Schema Changes

**None.** No model, migration, or new stored field. The page reads fields already present in
`backlog.EC`, `documents.DocumentVersion`, `workflow.Review`, and `accounts.User`.

## Pending Definition

An EC is pending validation when all of the following hold:

1. `EC.status == EC.Status.IN_VALIDATION`.
2. A latest `DocumentVersion` exists for the EC.
3. The latest `DocumentVersion` has no associated `Review` yet.
4. The EC has a `responsible_cd` assigned.

For a CD, additionally filter to `EC.responsible_cd == request.user`. For an Administrator, do not
apply that CD filter. Order newest submitted document first (`uploaded_at` descending), with a stable
EC identifier tie-breaker.

This definition excludes ECs without a document, already reviewed versions (approved or rejected),
cancelled ECs, and ECs whose current document is not awaiting a decision. A resubmitted new version
without a Review is pending again, provided the workflow has returned the EC to `IN_VALIDATION`.

## Input / Output

**Input:** HTTP GET `/backlog/pending-ecs/`; optional page number for pagination. No search or
additional filters in this first version.

**Access rules:**

| User | Result |
|---|---|
| Anonymous | 302 redirect to `LOGIN_URL` |
| CD | 200; only ECs assigned to that CD |
| Administrator | 200; all ECs satisfying the pending definition |
| Requester or DES Team | 403; no pending-queue data returned |

**Page/table output:**

- Portuguese page title: `Solicitações Pendentes`.
- Columns: EC ID/reference, Requester, Responsible CD, latest document version, document upload
  date/time, and an action linking to the EC detail page.
- Page size: 25 rows.
- Empty result: a clear Portuguese empty-state message (no blank table or error).
- The sidebar link is visible only to CD and Administrator, matching its current placement.

## Edge Cases

1. No eligible ECs → render the empty state with HTTP 200.
2. An EC has no `DocumentVersion` → exclude it from the pending queue.
3. The latest version already has a `Review` → exclude it, even if an older version has no review.
4. A rejected EC with no newer resubmitted version → exclude it; after a new unreviewed version is
   uploaded and status returns to `IN_VALIDATION`, include it.
5. A CD cannot see another CD's assigned EC, including by changing the page query string.
6. Administrator access is read-only; the page does not grant workflow decision permissions.
7. Multiple ECs with the same upload timestamp → stable ordering by EC year and sequence.

## Acceptance Criteria

1. `Solicitações Pendentes` links to the new page for CD and Administrator.
2. CD sees only their assigned, currently unreviewed latest document versions.
3. Administrator sees all ECs satisfying the pending definition.
4. Requester and DES Team receive 403; anonymous users are redirected to login.
5. Each listed EC links to its existing detail page; no new approval/rejection behavior is added.
6. Pagination and the empty state work.
7. Tests pass, `ruff check .` is clean, and no migration is generated.

## Decisions to Confirm Before `SPEC_APPROVED`

1. Confirm the proposed roles: CD sees assigned ECs; Administrator sees all pending ECs.
2. Confirm the pending definition requires an assigned CD and a latest document version without a
   Review. This follows the existing validation flow, but the SRD does not spell out a queue query.
3. Confirm the proposed columns and page size (25 rows).
