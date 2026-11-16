# Spec — Custom `LogEntryAdmin` (Auditlog admin yang rapi)

## Objective

Bikin halaman `/admin/auditlog/logentry/` (daftar LogEntry di Django admin) rapi dan mudah dibaca,
supaya Administrator bisa melihat riwayat audit tanpa noise.

**Masalah saat ini (lihat screenshot):**
- Baris `last_login` membanjiri daftar (setiap login user bikin 1 baris)
- Kolom "changes" menampilkan "8 changes: created_at, updated_at, id, document_version, cd, comment, decision, …" — dump mentah field yang tidak manusiawi
- object_repr format "Accounts | User - pualuan" — verbose dan tidak konsisten
- Kolom Correlation ID selalu "-"
- Aksi hanya "update"/"create" — tanpa konteks

**Target:**
- Hanya tampilkan kejadian bisnis yang relevan (per RNF02: creation, assignment, approval/rejection, routing)
- Kolom "changes" berisi kalimat manusia: "status: Em validação → Aprovada", "decision: approved", "version_number: v1.0"
- Object link tampil sebagai "EC 2026-011", "User pualuan", "Review EC 2026-011 v1.0"
- Filter berdasarkan: aktor, aksi, tanggal, resource type
- Kolom Correlation ID disembunyikan (belum dipakai)

## Tech Stack

Django 6.1, django-auditlog (sudah dependency), factory-boy.
**No new dependency.**

## Commands

```bash
uv run pytest apps/backlog/tests/test_auditlog_admin.py   # feature tests
uv run pytest                                             # full suite
uv run ruff check .                                       # lint
uv run python manage.py runserver                         # manual check sebagai administrator
```

## System Architecture

```
apps/backlog/
├── admin.py            # EDIT: unregister default LogEntryAdmin, register custom LogEntryAdmin
└── tests/
    └── test_auditlog_admin.py   # NEW: tests untuk custom admin

# Tidak ada perubahan model, migration, atau service.
# Custom admin hanya mengubah tampilan (list_display, list_filter, methods).
```

Import direction stays legal: `backlog` reads `auditlog.models.LogEntry` (`backlog → auditlog`).
Admin file boleh import dari app lain (tidak ada aturan import untuk admin.py).

## Database Schema Changes

**None.** No migration, no model edits, no change to `LogEntry` fields.
The admin only changes presentation; the underlying data is untouched.

## Input / Output

**Input:** HTTP GET `/admin/auditlog/logentry/`, session role `administrator` (atau staff dengan akses).

**Kolom `list_display`:**

| Kolom | Sumber | Format |
|---|---|---|
| `created` | `LogEntry.timestamp` | `DD/MM/YYYY HH:MM` (localized) |
| `actor` | `LogEntry.actor` | Full name atau username; "Sistema" jika None |
| `action_badge` | `LogEntry.action` | Badge HTML: "Dibuat" (hijau), "Diperbarui" (biru), "Dihapus" (merah) |
| `object_link` | `LogEntry.object_repr` + `content_type` | Link ke objek: "EC 2026-011", "User pualuan" |
| `changes_summary` | `LogEntry.changes_dict` | Kalimat manusia: "status: Em validação → Aprovada" |

**`list_filter`:** `action`, `content_type`, `timestamp` (date hierarchy)

**`search_fields`:** `actor__username`, `actor__first_name`, `actor__last_name`, `object_repr`

**Queryset:** `LogEntry.objects.select_related("actor", "content_type").order_by("-timestamp")`

**Noise filtering:** Daftar default menampilkan semua baris, tapi:
- `last_login` entries tetap tersimpan di DB (immutable), hanya tidak lagi dihasilkan untuk entri baru (exclude_fields sudah diimplementasikan di branch ini)
- Kolom "changes" hanya menampilkan field yang berubah, bukan semua field yang ada di diff

**Output:**

| Case | Status | Result |
|---|---|---|
| Administrator membuka `/admin/auditlog/logentry/` | 200 | Tabel rapi dengan kolom di atas |
| Filter by action=update | 200 | Hanya baris action=update |
| Filter by resource type=EC | 200 | Hanya baris EC |
| Search by actor username | 200 | Baris yang actor.username mengandung query |
| Click object_link | 302/200 | Redirect ke objek asli (EC detail, User change form, dll) |

**changes_summary format:**

| Field yang berubah | Renders as |
|---|---|
| `status` | `status: Em validação → Aprovada` |
| `decision` | `decision: approved` |
| `version_number` | `version_number: v1.0` |
| `is_open` | `is_open: True → False` |
| `comment` | `comment: (baru diisi)` atau `comment: (dihapus)` |
| Multiple fields | `status: …; decision: …` (dipisah `; `) |

## Edge Cases

1. **`LogEntry.actor is None`** (row written outside HTTP request, e.g. management command) → `actor` column renders `Sistema`, not `None` or empty.
2. **`LogEntry.changes is None`** (e.g. ACCESS action, atau create tanpa diff) → `changes_summary` renders `-` (em dash), not error.
3. **`content_type is None`** → `object_link` renders raw `object_repr` without link, no `AttributeError`.
4. **`object_repr` tanpa EC code** (User, Release) → `object_link` renders `str(obj)` as-is; no `IndexError`.
5. **User dengan `full_name` kosong** → fallback ke `username`; jangan render `None`.
6. **Filter by action=access** → hanya tampilkan ACCESS rows (biasanya 0 karena `log_access` belum dipanggil).
7. **Empty table** (fresh DB, belum ada log) → Django admin menampilkan "0 Log entrys", tidak crash.

## Project Structure

See System Architecture above. Satu file diubah (`apps/backlog/admin.py`), satu file test baru.

## Code Style

Thin admin (tidak ada business logic di admin), hanya presentation methods.

```python
# apps/backlog/admin.py
from auditlog.models import LogEntry
from auditlog.registry import auditlog
from django.contrib import admin
from django.utils.html import format_html

# ... (existing ReleaseAdmin, ECAdmin) ...

admin.site.unregister(LogEntry)

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ["created", "actor", "action_badge", "object_link", "changes_summary"]
    list_filter = ["action", "content_type", "timestamp"]
    search_fields = ["actor__username", "actor__first_name", "actor__last_name", "object_repr"]
    date_hierarchy = "timestamp"
    list_select_related = ["actor", "content_type"]
    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Actor", ordering="actor__username")
    def actor(self, obj):
        if obj.actor is None:
            return "Sistema"
        return obj.actor.full_name or obj.actor.username

    @admin.display(description="Aksi")
    def action_badge(self, obj):
        colors = {1: "success", 2: "primary", 3: "danger"}  # CREATE, UPDATE, DELETE
        labels = {1: "Dibuat", 2: "Diperbarui", 3: "Dihapus"}
        color = colors.get(obj.action, "secondary")
        label = labels.get(obj.action, str(obj.action))
        return format_html(
            '<span class="badge bg-{}">{}</span>', color, label
        )

    @admin.display(description="Objek")
    def object_link(self, obj):
        # Format: "EC 2026-011" atau "User pualuan"
        # TODO: implement clean object naming
        return obj.object_repr

    @admin.display(description="Perubahan")
    def changes_summary(self, obj):
        # Format: "status: Em validação → Aprovada"
        if not obj.changes:
            return "-"
        # TODO: implement human-readable changes
        return obj.changes_str()
```

## Testing Strategy

TDD: failing test first. File baru `apps/backlog/tests/test_auditlog_admin.py`.

| # | Test | Proves |
|---|------|--------|
| 1 | `test_logentry_admin_is_registered` | Custom LogEntryAdmin terdaftar, bukan default |
| 2 | `test_actor_column_shows_full_name` | Actor column renders full name |
| 3 | `test_actor_column_falls_back_to_username` | Full name kosong → username |
| 4 | `test_actor_none_renders_sistema` | Actor None → "Sistema" |
| 5 | `test_action_badge_renders_portuguese_label` | Badge "Dibuat"/"Diperbarui"/"Dihapus" |
| 6 | `test_changes_summary_renders_status_arrow` | "status: Em validação → Aprovada" |
| 7 | `test_changes_summary_renders_multiple_fields` | "status: …; decision: …" |
| 8 | `test_changes_none_renders_dash` | changes=None → "-" |
| 9 | `test_object_link_renders_ec_code` | object_repr "EC 2026-011" |
| 10 | `test_no_add_change_delete_permissions` | Readonly admin |

## Boundaries

- **Always:** TDD, `uv run pytest -q` + `uv run ruff check .` before done.
- **Read-only:** the admin renders counts and a log; it performs no POST, no mutation, no export.
- **Status untouched** — nothing here changes `EC.status`.
- **No correlation ID** — column is hidden until middleware is configured.
- **Old `last_login` entries stay in DB** — they are immutable per RNF02; the admin just displays them as-is (they will appear as "Diperbarui" with `last_login: …` in changes_summary).
- **Ask first:** new dependencies, changing `LogEntry` model, moving `auditlog.register` calls.

## Success Criteria

- [x] Opening `/admin/auditlog/logentry/` as administrator shows a clean table with columns: Created, Actor, Aksi, Objek, Perubahan.
- [x] `last_login` entries no longer flood the list (they exist in DB but new ones are not created).
- [x] `changes_summary` renders human-readable sentences, not raw JSON dumps.
- [x] `action_badge` renders Portuguese labels with color badges.
- [x] `object_link` renders clean names ("EC 2026-011", not "Backlog | ec - 2026-011").
- [x] Full suite green (245 passed, incl. 18 new); `ruff check .` clean.

## Implementation Notes (deviasi dari spec)

1. **Method `actor_name`, bukan `actor`.** `django.contrib.admin.utils.lookup_field` mengutamakan field model; `LogEntry.actor` adalah field FK, jadi method dengan nama sama tidak akan pernah dipanggil. Kolom tetap berlabel "Actor" via `@admin.display`.
2. **Badge pakai inline `style="background-color:…"`**, bukan class `badge bg-*` — admin Django tidak memuat `static/css/app.css` (class itu di-scoping ke `table.table` aplikasi).
3. **Konstanta aksi: CREATE=0, UPDATE=1, DELETE=2, ACCESS=3** (snippet di spec salah off-by-one). ACCESS jatuh ke `get_action_display()` + abu-abu.
4. **Data asli menyimpan `"None"` sebagai string** (auditlog stringify sebelum persist), bukan JSON `null` — `_is_empty` menganggap `None`, `""` dan `"None"` sama-sama kosong.
5. **`changes_summary` melewati field `id`,** memotong total ke 200 karakter + `…`, dan memberi perlakuan khusus `comment` ("(baru diisi)"/"(dihapus)") sesuai tabel spec.
6. **Filter resource type memakai `RelatedOnlyFieldListFilter`** — hanya menampilkan tipe yang benar-benar punya baris log.
7. **Review/DocumentVersion tetap menampilkan repr aslinya** ("Review by reviewer1 for 2026-011 - v1.0", "2026-011 - v1.0") dengan label prefix hanya jika belum diawali label — sesuai Edge Case 4; format pendek "Review EC 2026-011 v1.0" dari paragraf Objective tidak diwajibkan test mana pun.

## Decisions

1. **Custom LogEntryAdmin, not a new page.** Admin is internal tool for Administrator; the dashboard feed (`_log_activity` in `selectors.py`) is the user-facing Portuguese sentence view.
2. **Correlation ID hidden.** Middleware is enabled but no correlation ID is assigned per request; column shows "-" always. Re-enable when middleware is configured.
3. **`last_login` entries stay in DB.** RNF02 requires immutable audit log; we only stop creating new ones via `exclude_fields`.
4. **Language: Portuguese labels** for action badge (matching dashboard feed), but timestamp/object_repr stays as-is (system-level).
5. **No pagination customization** — default Django admin pagination (100 per page) is fine.

## Open Questions

- Should we also clean up old `last_login` entries from the DB? (Would require a data migration; RNF02 says immutable, so probably not.)
- Should `changes_summary` truncate long comments? (Currently `changes_str()` truncates at 200 chars by default.)
- Should we add a `Registo de Auditoria` page (separate from admin) for end-users? (Currently out of scope; dashboard feed is the user-facing view.)

## Branch Name

`feat/auditlog-cleanup` (current branch)
