# Spec: Application Release creation and capacity management

## Status

**Draft — requires user review and `SPEC_APPROVED` before implementation.**

## Objective

Provide Release creation and capacity management in the EC Backlog application
for users with the application role `Administrator`.

- An Administrator can create a Release and explicitly choose its capacity
  instead of silently using 10.
- An Administrator can later edit an existing Release, but capacity is the
  only editable field.
- The system continues to generate the Release ID, year, and sequence.
- These operations use the application UI and role permissions, not Django
  Admin.

## Requirement traceability

- **RF02:** The system generates/associates Releases, each grouping ECs. This
  feature exposes controlled Release creation and capacity configuration.
- **RNF01:** Only the Administrator application role can create Releases or
  change capacity. Authorization must be enforced server-side, not only by
  hiding UI controls.
- **RNF02:** Release creation and capacity changes remain recorded by the
  existing immutable `django-auditlog` history.

The SRD does not define a standalone Release administration workflow. The
architecture sets a maximum capacity of 10 ECs per Release; this draft keeps
that existing limit.

## User flow

1. An Administrator opens Release management in the EC Backlog application.
2. The list shows each Release, its EC occupancy, and capacity. It provides a
   **Nova Release** action and an edit-capacity action for each Release.
3. To create a Release, the Administrator opens the create form and enters a
   capacity from 1 to 10. Capacity is required in this form; the UI does not
   silently accept the model default of 10.
4. On submission, the system generates the next Release ID for the current
   year, sets `is_open=True`, saves the selected capacity, and returns to the
   list with a success message.
5. To edit a Release, the Administrator opens its capacity form. The form
   displays the Release code, current EC occupancy, and current capacity; only
   capacity can be changed.
6. Invalid submissions leave the stored Release data unchanged and display
   field-level validation errors.

## System architecture and affected components

The feature belongs to `apps/backlog`, which owns the `Release` model, Release
ID generation, and capacity rules. Views stay thin; write-side business rules
belong in `apps/backlog/services.py`.

Expected components to add or update:

- `apps/backlog/forms.py` — create form requiring capacity and update form
  exposing only capacity.
- `apps/backlog/services.py` — extend the existing Release creation service
  with an optional capacity parameter, preserving its default of 10 for the
  existing on-demand EC submission flow; add a capacity-update service that
  enforces Administrator authorization and capacity invariants.
- `apps/backlog/views.py` — authenticated, Administrator-only create and
  capacity-edit views.
- `apps/backlog/urls.py` — named application routes for Release creation and
  capacity editing.
- `apps/backlog/tables.py` and `templates/backlog/release_list.html` —
  Administrator-only create and per-Release capacity-edit actions.
- `templates/base.html` — link the Administrator's application navigation to
  Release management.
- `templates/backlog/release_form.html` and
  `templates/backlog/release_capacity_form.html` — create and edit forms using
  the existing Portuguese UI conventions.
- `apps/backlog/tests/` — tests for ID generation, capacity validation,
  permissions, updates, auditability, and existing on-demand behavior.

Do not use Django Admin for these operations. Keep imports within the
`backlog` app; no upward imports are required.

## Data model and migrations

`backlog.Release.capacity` already exists as a `PositiveSmallIntegerField`
with a default of 10. No new model field, constraint, or database schema change
is proposed, so no migration is expected. Application-driven Release creation
must pass the Administrator-selected capacity to the existing Release
creation service. The existing on-demand EC submission path continues to use
capacity 10 unless explicitly scoped separately.

The existing `django-auditlog` registration for `Release` must record both
creation and subsequent capacity changes.

## Inputs and outputs

### Create Release form input

```text
POST /backlog/releases/new/
capacity=<integer>
```

Capacity is required and must be an integer from 1 through 10. Release code,
year, sequence, and `is_open` are generated or set by the system; the client
cannot provide them.

### Edit capacity form input

```text
POST /backlog/releases/<release_id>/capacity/
capacity=<integer>
```

The edit form accepts only capacity and rejects missing, non-integer, zero,
negative, and values greater than 10. The Release identifier comes from the
URL and must resolve to an existing Release. No other Release field changes.

### Successful create output

- Create the next Release for the current year using the existing
  `TT_ON_AAAA-NNN` format and sequence rules.
- Persist the selected capacity and `is_open=True`.
- Redirect to the Release list and display a success message with the new code.
- Record the creation through the existing audit log.

### Successful edit output

- Persist the selected capacity for the existing Release, changing no other
  fields.
- Redirect to the Release list and display a success message.
- Record the capacity change through the existing audit log.

### Invalid or unauthorized output

- Invalid capacity: re-render the relevant form with validation errors; do not
  modify persisted data.
- Anonymous user: redirect to login, consistent with authenticated
  application views.
- Authenticated user whose application role is not `Administrator`: return
  HTTP 403 for direct GET and POST requests.
- Unknown Release ID on edit: return HTTP 404.

## Capacity rules and open decisions

1. **Allowed range:** preserve the architecture's maximum of 10 ECs; selected
   capacity must be from 1 to 10. The Administrator chooses the value per
   Release rather than being forced to use 10.
2. **Lowering below current occupancy:** proposed rule: reject a capacity
   smaller than the Release's current EC count, to avoid representing an
   already-over-capacity Release. **User confirmation required.**
3. **Closed Releases:** proposed scope permits editing any existing Release,
   including closed Releases. **User confirmation required** if closed
   Releases should instead be read-only.

These proposed decisions must be confirmed before implementation. The
architecture's maximum of 10 remains unchanged by this draft.

## Edge cases

| Case | Expected behavior |
|---|---|
| Create form omits capacity | Reject with a field error; do not silently use 10. |
| Capacity is not an integer, zero, or negative | Reject with a form error; stored data remains unchanged. |
| Capacity is greater than 10 | Reject with a form error. |
| Administrator creates Release with capacity 1–10 | Create it with the next generated Release ID and selected capacity. |
| Release year has no prior sequence | Generate sequence 001 for the current year. |
| Release ID collision occurs during concurrent creation | Preserve the existing service retry behavior; on exhaustion return a validation error and do not create a partial Release. |
| Capacity is lowered below current EC count | Reject if the proposed occupancy rule is confirmed. |
| Release does not exist on edit | Return HTTP 404. |
| Request is made by requester, CD, or DES Team | Deny direct GET/POST with HTTP 403. |
| User is logged out | Redirect to login. |
| Existing on-demand EC submission creates a Release | Continue using capacity 10 and existing atomic/rollback behavior. |
| Two Administrators update capacity close together | Validate against the latest persisted EC count inside the service transaction; do not rely on SQLite `select_for_update()` for row-level locking. |

## Acceptance criteria

- An Administrator can see existing Release codes, occupancy, and capacities
  in the application.
- An Administrator can create a Release through the application and choose a
  required capacity from 1 through 10.
- The Release code, year, and sequence are generated automatically.
- An Administrator can edit the capacity of an existing Release through the
  application; no other Release field is editable in that flow.
- Values outside the approved range are rejected without database changes.
- Capacity cannot be reduced below occupancy if that proposed rule is
  confirmed.
- Non-Administrator users cannot create or edit Releases by navigating
  directly to the URLs.
- Successful creation and capacity updates are represented in the audit log.
- Existing on-demand Release creation and EC capacity enforcement continue to
  work.
- No schema migration is introduced.

## Test plan

Write tests first (TDD):

1. Administrator can access the Release list, create form, and capacity-edit
   form.
2. Requester, CD, and DES Team receive HTTP 403 for direct GET and POST to
   create/edit routes; anonymous users are redirected to login.
3. Creating a Release with capacity 1, an intermediate value, and 10 saves the
   chosen capacity and generates the next expected Release ID.
4. Create submission without capacity or with invalid/out-of-range values is
   rejected and creates no Release.
5. Editing a Release updates only capacity; other Release fields remain
   unchanged.
6. Invalid capacity changes leave the database unchanged.
7. Capacity below existing EC occupancy is rejected if confirmed.
8. Unknown Release ID on edit returns HTTP 404.
9. Audit log contains Release creation and capacity update records.
10. Existing on-demand EC creation continues to create its Release with
    capacity 10; invalid EC/document submissions do not leave orphan Releases.
11. Existing EC creation refuses assignment when the configured Release
    capacity is reached.

## Out of scope

- Deleting Releases.
- Manually entering or editing Release codes, years, or sequence numbers.
- Manually changing `is_open` or Production Go-Live Date from these forms.
- Changing the architecture's maximum capacity above 10.
- Editing Releases through Django Admin.
- Changing the `Release` database schema.
