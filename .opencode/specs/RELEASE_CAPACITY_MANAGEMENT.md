# Spec: Administrator-managed Release capacity

## Status

**Draft — requires user review and `SPEC_APPROVED` before implementation.**

## Objective

Provide a page in the EC Backlog application where a user with the application
role `Administrator` can view existing Releases and change their EC capacity.
This is for editing existing Releases; creating a new Release is a separate
workflow and is out of scope for this feature.

## Requirement traceability

- **RF02:** Release association and capacity governs how many ECs a Release can
  group. This feature provides controlled administration of that existing
  capacity value.
- **RNF01:** Only the Administrator application role can access and submit
  capacity changes; authorization must be enforced by the server-side view and
  service, not only by hiding UI controls.
- **RNF02:** Changes to `Release.capacity` must remain visible in the existing
  immutable audit trail provided by `django-auditlog`.

The SRD does not define a separate capacity-editing workflow. The architecture
currently states that a Release has a maximum capacity of 10 ECs; that limit is
preserved in this draft.

## User flow

1. An Administrator opens the Release capacity management page from the
   application navigation or Release management page.
2. The page lists Releases and their current EC count and capacity.
3. The Administrator selects a Release and opens its capacity edit form.
4. The form shows the Release code, current occupancy, and current capacity;
   only the capacity is editable.
5. On a valid submission, the application saves the capacity, records the
   change through the existing audit log, and returns the Administrator to the
   Release list with a success message.
6. Invalid submissions leave the stored capacity unchanged and display a
   field-level validation error.

## System architecture and affected components

The feature belongs to `apps/backlog`, which owns `Release`, capacity rules,
and Release management. Keep views thin and put the capacity update rule in a
backlog service.

Expected components to add or update:

- `apps/backlog/forms.py` — a focused form exposing only `capacity`.
- `apps/backlog/services.py` — an update service enforcing administrator
  authorization and capacity invariants.
- `apps/backlog/views.py` — authenticated, Administrator-only list/edit views.
- `apps/backlog/urls.py` — named routes for the capacity management and edit
  pages.
- `apps/backlog/tables.py` and/or `templates/backlog/release_list.html` — an
  Administrator-only edit action for each existing Release.
- `templates/base.html` — link the Administrator configuration navigation to
  the capacity management page.
- `templates/backlog/release_capacity_list.html` and
  `templates/backlog/release_capacity_form.html` — list and edit UI, following
  existing Portuguese UI conventions.
- `apps/backlog/tests/` — service and view tests for validation, permissions,
  successful edits, and auditability.

Do not use Django Admin for this feature. Do not implement Release creation as
part of these screens. Keep all model and service imports within the existing
`backlog` app; no upward imports are needed.

## Data model and migrations

`backlog.Release.capacity` already exists as a `PositiveSmallIntegerField`
with a default of 10. No new model field, constraint, or database schema change
is proposed; therefore no migration is expected. Update the existing field
through the backlog service and preserve its current auditlog registration.

## Input and output

### Edit form input

```text
POST /backlog/releases/<release_id>/capacity/
capacity=<integer>
```

The form must reject missing, non-integer, zero, negative, and values greater
than 10. The Release identifier comes from the URL and must resolve to an
existing Release. No other Release fields may be accepted from the form.

### Successful output

- Persist the new capacity for the selected Release.
- Return a redirect to the Release capacity list.
- Show a success message naming the Release.
- Ensure the new value is recorded in `django-auditlog`.

### Invalid or unauthorized output

- Invalid capacity: re-render the form with validation errors; do not update
  the Release.
- Anonymous user: redirect to login, consistent with existing authenticated
  application views.
- Authenticated user whose application role is not `Administrator`: return
  HTTP 403 for direct GET and POST requests.
- Unknown Release ID: return HTTP 404.

## Capacity rules and open decisions

1. **Maximum capacity:** this draft preserves the architecture's maximum of
   10 ECs. The feature does not permit capacity values greater than 10.
2. **Lowering below current occupancy:** proposed rule: reject a capacity
   smaller than the Release's current EC count. This avoids representing a
   Release as already over capacity. **User confirmation required.**
3. **Closed Releases:** proposed scope allows editing capacity for any existing
   Release, including closed Releases, because the request says existing
   Release capacity. **User confirmation required** if closed Releases should
   instead be read-only.

These decisions must be confirmed before implementation. No capacity value
change may bypass the constraints in this spec after approval.

## Edge cases

| Case | Expected behavior |
|---|---|
| Capacity is omitted or not an integer | Reject with a form error; stored value remains unchanged. |
| Capacity is 0 or negative | Reject with a form error. |
| Capacity is greater than 10 | Reject with a form error. |
| Proposed capacity is below current EC count | Reject if the proposed occupancy rule is confirmed. |
| Release does not exist | Return HTTP 404. |
| Request is made by requester, CD, or DES Team | Deny direct GET/POST with HTTP 403. |
| User is logged out | Redirect to login. |
| POST is invalid or authorization fails | Do not modify the Release or its EC associations. |
| Two administrators update a capacity close together | Validate against the latest persisted EC count and capacity in the service transaction; do not rely on SQLite `select_for_update()` for row locking. |

## Acceptance criteria

- An Administrator can open the capacity management page and see existing
  Release codes, current occupancy, and current capacity.
- An Administrator can edit the capacity of an existing Release using the
  application UI without entering Django Admin.
- Only the capacity field is changed by the edit form.
- Values outside the approved range are rejected without modifying the
  database.
- Capacity cannot be reduced below occupancy if that proposed rule is
  confirmed.
- Non-Administrator users cannot access or submit the update by navigating
  directly to the URL.
- Successful changes appear in the existing audit log.
- Existing Release creation, EC assignment, and capacity enforcement
  behavior continue to work.
- The implementation adds no schema migration unless later approval changes
  this data contract.

## Test plan

Add tests before implementation (TDD):

1. Administrator can access the list and edit form.
2. Requester, CD, and DES Team receive 403 for direct GET and POST.
3. Anonymous users are redirected to login.
4. Valid capacity updates the selected Release and redirects with success.
5. Missing, non-integer, zero, negative, and above-10 values are rejected;
   database values remain unchanged.
6. Capacity below current occupancy is rejected if confirmed.
7. Unknown Release ID returns 404.
8. A successful capacity update generates an auditlog update.
9. Existing capacity checks in EC creation still refuse an EC when the
   Release's configured capacity is reached.

## Out of scope

- Creating or deleting Releases.
- Changing Release codes, years, sequence numbers, or go-live dates.
- Opening or closing Releases manually.
- Raising the architecture's maximum capacity above 10.
- Editing capacity through Django Admin.
- Changing the `Release` database schema.
