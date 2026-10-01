# EC Backlog Management — Database Schema Spec

**Status:** Approved and fully implemented. Sections 4.1–4.4 (`core.TimeStampedModel`, `accounts.User`, `backlog.Release`, `backlog.EC`) were approved on 2026-09-29. Sections 4.5–4.6 (`documents.DocumentVersion`, `workflow.Review`) were approved and implemented on 2026-10-01, with the two naming decisions recorded as #12 and #13 in the decisions log (section 9).
**Suggested location:** `.opencode/specs/database-schema.md`
**Sources:** SRD v1.1 (RF01–RF12, RNF01–RNF06), `docs/ARCHITECTURE.md`, and the design decisions made with the user on 2026-09-29 (see section 9).

> Read `docs/ARCHITECTURE.md` first. If anything here conflicts with it, stop and ask the user.

---

## 1. Scope

This spec defines the database models for the EC Backlog Management System: users (already exist), Releases, ECs, document versions, and reviews. It also defines the business rules the services must enforce and the items that are deliberately **not** tables (audit trail, notifications).

Rules that apply to everything below:

- Package manager is **uv only**. Commands: `uv run python manage.py ...`.
- Business logic lives in `services.py` / `selectors.py`, never in views or models' `save()`.
- `EC.status` is changed **only** by `workflow` service functions (one documented exception: the historical import, section 7.7).
- Every multi-step write uses `transaction.atomic()`.
- Do not use engine-specific features (raw SQL, vendor-only field types). The engine is **SQLite in both development and production**, decided 2026-09-29; see `docs/ARCHITECTURE.md` section 2 for what that costs.
- All foreign keys use `on_delete=PROTECT`. History must never be deleted by accident.
- After changing any model, follow `.opencode/skills/django-db-integrity/SKILL.md`. Implement with `.opencode/skills/django-tdd-loop/SKILL.md`.

---

## 2. Apps and model ownership

Dependency rule: `workflow → documents → backlog → accounts`. `core` may be imported by anyone and imports nothing.

| App | Models | Notes |
|---|---|---|
| `core` | `TimeStampedModel` (abstract) | Currently empty; must be created |
| `accounts` | `User` | Already exists and is migrated. Field set confirmed against the real model in 4.2 |
| `backlog` | `Release`, `EC` | |
| `documents` | `DocumentVersion` | FK to `"backlog.EC"` by string |
| `workflow` | `Review` | FK to `"documents.DocumentVersion"` by string |

---

## 3. ERD overview

```
                    ┌──────────┐
                    │ Release  │
                    └────┬─────┘
                         │ 1
                         │
                         │ N
 User ──(requester)──< EC >──(responsible CD)── User
                         │ 1
                         │
                         │ N
                 ┌───────┴────────┐
                 │ DocumentVersion│>── User (uploaded_by)
                 └───────┬────────┘
                         │ 1
                         │
                         │ 0..1
                 ┌───────┴────────┐
                 │     Review     │>── User (cd)
                 └────────────────┘
```

Audit trail: provided by `django-auditlog` (no custom table). Notifications: `django-q2` (no table).

---

## 4. Tables

The **ERD name** column maps each field to the name used in the original dbdiagram.io ERD. **Use the Django field name** in the code.

### 4.1 `core.TimeStampedModel` (abstract)

| Django field | Type | Notes |
|---|---|---|
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

Not drawn in the ERD. `Release`, `EC`, `DocumentVersion`, and `Review` inherit from it. `DocumentVersion` also has its own `uploaded_at` and `Review` has `decided_at`, which are business dates.

### 4.2 `accounts.User` (existing)

Extends `AbstractUser`. Existing table `accounts_user`.

| ERD name | Django field | Notes |
|---|---|---|
| `id` | `id` | |
| `name` | `name` | `CharField(max_length=150, blank=True)`. The real model has a dedicated `name` column. `first_name` / `last_name` are inherited from `AbstractUser` and intentionally left unused; display via `name` or the `full_name` property (decision: removed the `save()` sync, 2026-10-01) |
| `email` | `email` | `EmailField(unique=True)`, inherited from `AbstractUser` and tightened to unique |
| `role` | `role` | `CharField(max_length=20, choices=Role.choices)`; values: `requester`, `cd`, `des_team`, `administrator`. Default `requester` |
| `active` | `is_active` | Inherited from `AbstractUser`. **Not redeclared** in the model: an explicit redeclaration only produced a no-op migration |

`Role` is a nested `models.TextChoices` class on `User`. Permission checks use `user.role == User.Role.CD`, never a bare string.

### 4.3 `backlog.Release`

Table: `backlog_release`. One Release groups many ECs.

| Django field | ERD name | Type | Null | Constraints / notes |
|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | no | PK (default) |
| `release_code` | `release_code` | `CharField(max_length=20)` | no | **UNIQUE**. Format `TT_ON_YYYY-NNN` (e.g. `TT_ON_2026-007`). Built only by the service that creates the Release. Never user-editable |
| `year` | `year` | `PositiveSmallIntegerField` | no | |
| `number_sequence` | `number_sequence` | `PositiveIntegerField` | no | Number within the year, starting at 1 |
| `capacity` | (new) | `PositiveSmallIntegerField(default=10)` | no | Maximum ECs. **Never modified by a service** |
| `is_open` | (new) | `BooleanField(default=True)` | no | `False` = closed to new ECs (see rules in 7.2 and 7.3) |
| `production_go_live_date` | `production_go_live_date` | `DateField` | **yes** | Set manually by DES after implementation (RF04). Applies to all ECs in the Release |

Constraints:

- `UniqueConstraint(fields=["year", "number_sequence"], name="release_year_number_uniq")`

Meta: `db_table = "backlog_release"`, `ordering = ["-year", "-number_sequence"]`.

Python helpers (not stored):

```python
@property
def ec_count(self):
    return self.ecs.count()


@property
def is_full(self):
    return self.ec_count >= self.capacity
```

On list pages use `annotate(Count("ecs"))` instead of `ec_count` to avoid N+1 queries.

### 4.4 `backlog.EC`

Table: `backlog_ec`.

| Django field | ERD name | Type | Null | Constraints / notes |
|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | no | PK. Internal only; users never see it and the import never sets it |
| `year` | `year` | `PositiveSmallIntegerField` | no | Set automatically from `creation_date` for new ECs |
| `number_sequence` | `number_sequence` | `PositiveIntegerField` | no | Number within the year: 1, 2, 3... Historical numbers are imported into this field |
| `reference` | `cr_rt_me_reference` | `CharField(max_length=50)` | no | Free text: CR2026003, `RT No. 29411`, COR2026001, etc. **No strict format validation** |
| `description` | `description` | `TextField` | no | |
| `requester` | `id_solicitante` | FK → `accounts.User` | **yes** | `related_name="requested_ecs"`. Null only for imported ECs. Set from the session for new ECs |
| `release` | `id_release` | FK → `backlog.Release` | **yes** | `related_name="ecs"`. **Nullable**: historical ECs may have no Release in the source Excel (resolved 2026-09-29) |
| `responsible_cd` | `cd_responsavel_id` | FK → `accounts.User` | **yes** | `related_name="assigned_ecs"`. The **currently** assigned CD. Null until assigned and for imported ECs |
| `creation_date` | `creation_date` | `DateField` | **yes** | Recorded at submission. Null for imported ECs that lack it |
| `status` | `status` | `CharField(max_length=20, choices=Status.choices)` | no | Default `in_validation`. Changed only by `workflow` services |
| `implemented_at` | (new) | `DateTimeField` | **yes** | Set automatically when DES closes the EC. Null for imported ECs |
| `is_imported` | (new) | `BooleanField(default=False)` | no | `True` for rows loaded from the historical Excel |

`Status` values (`models.TextChoices`):

| Stored value | Label |
|---|---|
| `in_validation` | In Validation |
| `approved` | Approved |
| `rejected` | Rejected |
| `sent_to_des` | Sent to DES |
| `closed` | Closed |
| `cancelled` | Cancelled |

Constraints and indexes:

- `UniqueConstraint(fields=["year", "number_sequence"], name="ec_year_number_uniq")`
- Indexes on `status` and `creation_date` (FKs `requester` and `release` are indexed automatically). These support the RF12 filters: EC ID, Release, Status, date, requester.

Computed (not stored):

```python
@property
def ec_code(self):
    return f"{self.year}-{self.number_sequence:03d}"  # e.g. 2026-001
```

The EC ID users see is year + number. The bare number (`001`) repeats every year, so always show the year next to it.

**Removed from the original ERD:** `esc_code` (replaced by the computed `ec_code`) and `rejection_comment` (moved to `Review`).

### 4.5 `documents.DocumentVersion`

Table: `documents_documentversion`.

| Django field | ERD name | Type | Null | Constraints / notes |
|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | no | PK |
| `ec` | `ec_id` | FK → `"backlog.EC"` | no | `related_name="versions"` |
| `version_number` | `version_number` | `CharField(max_length=10)` | no | `v1.0`, `v1.1`, `v2.0`. Incremented automatically by the service |
| `file` | `file_path` | `FileField(upload_to=...)` | no | Stored under `MEDIA_ROOT`, outside the code tree. Validate type (`.docx`, `.pdf`) and size |
| `uploaded_by` | `uploaded_by` | FK → `accounts.User` | no | `related_name="uploaded_versions"` |
| `uploaded_at` | `upload_date` | `DateTimeField(auto_now_add=True)` | no | |
| `change_reason` | `change_reason` | `TextField(blank=True)` | no | What the **requester** changed. Empty for `v1.0`, **required** for every later version (enforced in the upload service) |

Constraints:

- `UniqueConstraint(fields=["ec", "version_number"], name="docversion_ec_version_uniq")`

The current version of an EC is its latest version: `ec.versions.order_by("-id").first()`. All previous versions are kept (RF05).

### 4.6 `workflow.Review`

Table: `workflow_review`. **New table.** One row per CD decision, tied to the exact document version that was judged. A version with no row is **pending**.

| Django field | Type | Null | Constraints / notes |
|---|---|---|---|
| `id` | `BigAutoField` | no | PK |
| `document_version` | `OneToOneField("documents.DocumentVersion")` | no | `related_name="review"`. UNIQUE by definition (one review per version) |
| `cd` | FK → `accounts.User` | no | `related_name="cd_reviews"`. The CD who actually decided. Role-prefixed to match `requested_ecs` / `assigned_ecs` |
| `decision` | `CharField(max_length=10, choices=Decision.choices)` | no | `approved` or `rejected` |
| `comment` | `TextField(blank=True)` | no | The CD's reason. **Required when rejected**. Optional when approved |
| `decided_at` | `DateTimeField(auto_now_add=True)` | no | Business date of the decision, separate from `created_at` / `updated_at`. Stamped on first save, like `DocumentVersion.uploaded_at` |

Constraint:

```python
models.CheckConstraint(
    condition=~models.Q(decision="rejected") | ~models.Q(comment=""),
    name="review_rejection_requires_comment",
)
```

Use `condition=` (not the deprecated `check=`) on Django 6.1.

`Review.comment` (written by the CD) is different from `DocumentVersion.change_reason` (written by the requester). Keep both.

---

## 5. Relationships

| One | Many | Via | Meaning |
|---|---|---|---|
| `Release` | `EC` | `EC.release` | A Release groups many ECs (max `capacity`). `EC.release` is nullable, so an EC may have no Release |
| `User` | `EC` | `EC.requester` | A requester creates many ECs |
| `User` | `EC` | `EC.responsible_cd` | A CD is assigned many ECs |
| `EC` | `DocumentVersion` | `DocumentVersion.ec` | An EC has many versions |
| `User` | `DocumentVersion` | `DocumentVersion.uploaded_by` | A user uploads many versions |
| `DocumentVersion` | `Review` | `Review.document_version` | **1:1**, at most one review per version |
| `User` | `Review` | `Review.cd` | A CD makes many decisions |

---

## 6. EC status flow

```
In Validation ──approve──> Approved ──route to DES──> Sent to DES ──DES closes──> Closed
      │  ▲
   reject │ new version uploaded + CD reassigned
      ▼  │
   Rejected
```

| From | To | Action | Who (role) | Side effects |
|---|---|---|---|---|
| (new) | In Validation | Create EC and upload `v1.0` | Requester | Assign EC number and Release; notify CD on assignment (RF08) |
| In Validation | Approved | `approve_ec` | CD | Create `Review(approved)`; notify requester (RF10) |
| In Validation | Rejected | `reject_ec` | CD | Create `Review(rejected)` with **required** comment; notify requester with the comment (RF10) |
| Rejected | In Validation | Requester uploads a new version and assigns a CD | Requester | New `DocumentVersion` (version auto-incremented); notify CD |
| Approved | Sent to DES | `route_to_des` | CD (see open item 2) | Notify DES users |
| Sent to DES | Closed | `close_ec` | DES team | Set `implemented_at = now`; then re-check Release closing (7.3) |
| any non-final | Cancelled | `cancel_ec` | not defined yet (open item 3) | |

Roles are enforced in the services, not only in templates (RNF01).

---

## 7. Business rules (services)

### 7.1 EC number generation (`backlog/services.py`)

- Numbering **restarts every year**: `001`, `002`, ... per year.
- Inside `transaction.atomic()`: next number = `Max(number_sequence)` for that year + 1 (start at 1).
- `UNIQUE(year, number_sequence)` is the safety net. On `IntegrityError`, retry (a small fixed number of times).
- `year` is taken from `creation_date`; the user never types it.
- Imported ECs keep their historical `number_sequence`. The auto-increment `id` is never set by the import.

### 7.2 Assigning an EC to a Release (`backlog/services.py`)

- Runs inside `transaction.atomic()`, so two simultaneous submissions can never create an 11th EC. The guard is **SQLite's exclusive write lock, not row-level locking**: `select_for_update()` is a silent no-op on this engine (`has_select_for_update = False`), so do not call it and do not write code that assumes it works.
- The requester may pick an open Release, otherwise the service uses the oldest open Release. It re-checks capacity inside the transaction, **before** writing.
- A concurrent submission that loses the write lock fails with `OperationalError: database is locked`. The service must not convert that into a validation message; retrying is acceptable, surfacing it as a server error is not.
- **Test is required, sequentially.** Capacity is proved by showing the 11th EC is refused. Do not write a concurrent-write test here: SQLite's whole-file write lock makes such a test pass no matter what the code does, which is false evidence rather than assurance. If the project moves to PostgreSQL, restore `select_for_update()` and only then is a real concurrency test meaningful.
- If no open Release has room, create the next Release: current year, next `number_sequence`, `release_code = f"TT_ON_{year}-{number:03d}"`.
- After adding the EC, if `ec_count >= capacity`, set `is_open = False`. `capacity` itself is never changed.

### 7.3 When a Release closes (`is_open = False`)

A Release stops being open in exactly two cases:

1. **Full:** it reached `capacity` ECs (even if some ECs are not finished yet).
2. **Finished:** it has at least one EC, every non-cancelled EC is `Closed`, **and** `production_go_live_date` is set.

The service re-checks case 2 after every `close_ec` and after every go-live date entry, so the order of those two steps does not matter. A Release with a single EC follows the same rule. Cancelled ECs do not block closing. An empty new Release never counts as "all closed".

### 7.4 Versioning (`documents/services.py`)

- First upload creates `v1.0`.
- Every later upload increments the version automatically and requires `change_reason`.
- Previous versions are never modified or deleted.
- After a rejection, the new upload moves the EC back to `In Validation` (through a `workflow` service) and the requester assigns a CD again. The CD may be a different person.

### 7.5 Review (`workflow/services.py`)

- `approve_ec(ec, cd_user, comment="")` and `reject_ec(ec, cd_user, comment)` create the `Review` row, change `ec.status`, and queue the notification, all in one `transaction.atomic()`.
- Only the **current** (latest) version can be reviewed, and only once.
- Rejecting without a comment must fail in the service and at the database (`CheckConstraint`).

### 7.6 DES steps (`workflow/services.py`)

- `route_to_des(ec, user)`: `Approved` → `Sent to DES`, notify the DES users.
- `close_ec(ec, des_user)`: `Sent to DES` → `Closed`, set `implemented_at`. Only role `des_team`.
- `record_go_live_date(release, date, des_user)`: sets `Release.production_go_live_date` (one date for the whole Release). Only role `des_team`. Then re-check Release closing (7.3).
- DES can implement an EC as soon as it is approved and sent. It does not wait for other ECs in the same Release.

### 7.7 Historical import (`backlog/resources.py` + management command)

- Uses django-import-export with dry-run preview (RNF04). Excel needs `django-import-export[xlsx]`.
- Reads year and number from the Excel and writes them to `year` / `number_sequence`.
- Sets `is_imported = True`. Leaves `requester`, `responsible_cd`, `creation_date`, `implemented_at` empty.
- Creates missing Releases (with `release_code`, `year`, `number_sequence` parsed from the code) and applies the closing rule 7.3 to them.
- Imported ECs get status `closed` when their Release has a go-live date. Other cases: open item 5.
- **Documented exception to the "status only via workflow" rule:** an imported historical row has an initial status, not a transition, and `backlog` must not import from `workflow`. Set it in the import resource only.
- Correction releases exist in the history (e.g. `COR2026001 — Correction to release TT_ON_2026-004`); the `reference` field must accept them.

---

## 8. Audit and notifications (no custom tables)

**Audit trail (RNF02): `django-auditlog`.**

- Register `EC`, `Release`, `DocumentVersion`, and `Review`.
- Add `auditlog.middleware.AuditlogMiddleware` to `MIDDLEWARE` (after `AuthenticationMiddleware`) so web requests record the actor. It is **not** in `base.py` yet.
- Changes made outside a request (import command, django-q2 tasks) must set the actor explicitly.
- Never expose edit or delete of log entries, including in the admin.

**Notifications (RF08, RF10, RNF03): `django-q2`.**

- Emails are sent as django-q2 tasks from `workflow/notifications.py`, using the existing `Q_CLUSTER` retry settings.
- Queue them with `transaction.on_commit(...)` so nobody is emailed about a rolled-back change.
- On final failure, alert an administrator. There is **no** notification table.

---

## 9. Decisions log (changes from the original ERD)

| # | Topic | Original ERD | Final decision |
|---|---|---|---|
| 1 | Rejection comments | `ECS.rejection_comment` (one value, overwritten on each rejection) | Removed. New `workflow.Review` table, one row per decision, 1:1 with `DocumentVersion` |
| 2 | Release state | No open/closed state or uniqueness | Added `is_open`, `capacity` (default 10), `UNIQUE(release_code)`, `UNIQUE(year, number_sequence)` |
| 3 | EC identity | `id`, `year`, `number_sequenci`, `esc_code` | `year` + `number_sequence` (unique together, numbering restarts yearly); `esc_code` removed (computed `ec_code`) |
| 4 | Legacy data | All fields required | `requester`, `responsible_cd`, `creation_date` nullable; `is_imported` added. No placeholder user |
| 5 | Audit | Custom `audit_logs` table | Dropped. `django-auditlog` only |
| 6 | Notifications | No tracking | No table. django-q2 retries and failure alerts only |
| 7 | DES routing | Only the status value | Status flow with explicit "Sent to DES" click; `implemented_at` on EC; go-live date stays on Release and applies to all its ECs |
| 8 | Release closing | Not defined | Closed when full, or when all ECs are Closed and the go-live date is set |
| 9 | Naming | Mixed Portuguese/English, typos (`number_sequenci`, `teks`) | English Django names (mapping in section 4). Typos fixed |
| 10 | Timestamps | Existing abstract model used `created` / `updated` | Renamed to `created_at` / `updated_at` (section 4.1) via `RenameField`, so no data is lost |
| 11 | `EC.release` | `NOT NULL` | **Nullable**, so legacy Excel rows without a Release still import (2026-09-29) |
| 12 | `Review.cd` related_name | `reviews` | **`cd_reviews`**, chosen with the user on 2026-10-01. `user.reviews` read as "reviews *of* this user" rather than "reviews *made by*"; the role prefix matches `requested_ecs` and `assigned_ecs` |
| 13 | `Review.decision` choices | flat `approved` / `rejected` | Nested `Decision` `models.TextChoices` on the model, matching the `EC.Status` pattern in 4.4, so services compare against `Review.Decision.REJECTED` instead of a bare string |

---

## 10. Open items (do not invent answers; ask the user)

1. **Version numbering:** what triggers `v2.0` instead of `v1.1`? The SRD gives only the examples (v1.0, v1.1, v2.0). Until answered, implement automatic minor increments only.
2. **Who routes to DES:** the user says the CD; SRD RF11 says "the team". Confirm with TT.
3. **Cancelled:** who can cancel, from which statuses, and can it be reopened?
4. ~~**Historical Releases:** does every historical EC have a Release in the Excel?~~ **RESOLVED 2026-09-29: `EC.release` is nullable.** Imported rows may have no Release; the import service must tolerate `release is None`, and such ECs do not count toward any Release capacity.
5. **Imported status:** which status for imported ECs whose Release has no go-live date (e.g. EC 3 in the SRD annex)?
6. **Upload limits:** maximum file size and allowed extensions beyond `.docx` and `.pdf`.
7. ~~**Database engine:** SQLite vs PostgreSQL.~~ **RESOLVED 2026-09-29: SQLite in both development and production.** Consequences recorded in `docs/ARCHITECTURE.md` section 2 — one writer at a time, `select_for_update()` silently ignored, and the capacity rule (7.2) is guaranteed by SQLite's exclusive write lock instead of row-level locking.
8. **Release closing rule (7.3, case 2):** assumed both conditions are required (all ECs Closed **and** go-live date set). Confirm.
9. **EC ID display format:** ~~`2026-001` or `001/2026`.~~ **Implemented as `2026-001`** (spec 4.4, `EC.ec_code`). Only the presentation layer is affected if TT wants `001/2026`.
10. **Go-live date edits:** who may change it after it is set (it is audited either way).

---

## 11. Implementation order and required tests

Order (one migration set per step, following the `django-db-integrity` skill):

1. `core`: `TimeStampedModel`.
2. `backlog`: `Release`, then `EC`, plus admin registration and auditlog registration.
3. `documents`: `DocumentVersion`.
4. `workflow`: `Review`.
5. Add `AuditlogMiddleware` to settings.
6. Services and selectors for each app, driven by the tests below (TDD: failing test first).

Required tests (from `docs/ARCHITECTURE.md`, extended for these decisions):

- Release capacity, tested **sequentially**: the 11th EC is refused and the Release flips to `is_open = False`. No concurrent-write test — see 7.2 for why it would pass for the wrong reason.
- Release closes when full, and when all ECs are Closed with the go-live date set (either order).
- EC number generation: restarts each year, unique per year, retry on conflict, imported numbers never collide.
- Version increment on resubmission; `change_reason` required after `v1.0`; old versions preserved.
- Review: rejection requires a comment (service and database constraint); one review per version; only the current version can be reviewed.
- Status transitions and who may perform them (Requester, CD, DES team, Administrator).
- `implemented_at` is set on close; go-live date applies to the whole Release.
- Notification sending queued on commit, and failure handling.
- Excel import dry-run and real import: legacy rows load with nullable fields, `is_imported = True`, IDs preserved.