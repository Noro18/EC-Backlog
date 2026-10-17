# Spec — Document Versions Page (`Versões de Documentos`)

**Status:** SPEC_DRAFT — waiting for `SPEC_APPROVED`, plus two open decisions recorded in
"Approved Decisions" below.

## Objective

Give the Administrator a dedicated, read-only page listing every document version across all ECs,
replacing the `#` placeholder behind `Versões de Documentos` in the Administrator sidebar.

- Row = one `DocumentVersion` of one `EC`, newest uploads first.
- Each row shows enough metadata to identify the version (EC, version number, uploader, uploaded
  date/time, change reason) and offers two read-only actions: inline preview (modal) and original
  download.
- Each row may show a small thumbnail of the document's first page (decision-dependent; see
  Decisions and "Thumbnail Behaviour").
- The page writes nothing: uploading, deleting, and version numbering stay with the existing
  RF03 (create EC with document) and RF05 (re-upload new version) flows, and `workflow` keeps
  owning every status change.

This feature is derived from RF05 (automatic versioning / version history), RF06 (attached
document), RF12 (consultation), RNF01 (role-based access), and RNF05 (usability). The SRD does not
describe an admin-wide document-versions page; this spec proposes it as the read-only consultation
view the sidebar item has always promised.

## Tech Stack

Django 6.1, `django-tables2`, existing `DocumentVersion`, `EC`, and `User` models, and the existing
`documents:preview` / `documents:download` endpoints. **No new Python dependency.**
Thumbnail rendering (decision A only) reuses vendored **PDF.js 4.10.38** static assets — no CDN.

## Commands

```bash
uv run pytest apps/backlog/tests/test_document_versions_view.py  # feature tests
uv run pytest                                                    # full suite
uv run ruff check .                                              # lint
uv run python manage.py runserver                                # manual check as Administrator
```

## System Architecture

```
apps/backlog/
├── selectors.py   # add document_versions(q=None): versions across all ECs w/ EC + uploader
├── tables.py      # add DocumentVersionTable: mirrors the page columns
├── views.py       # add DocumentVersionsListView (login + Administrator check, 25/page, ?q=)
├── urls.py        # add /backlog/document-versions/ route (name: document_versions)
└── tests/
    └── test_document_versions_view.py  # NEW: access, contents, search, ordering, empty state

templates/backlog/
└── document_versions.html  # NEW: Portuguese title, search, table, modal, empty state

static/js/
└── document_thumbnails.js  # NEW (decision A only): lazy first-page thumbnails via PDF.js

templates/base.html  # EDIT: replace the `Versões de Documentos` `#` link with the named route
docs/ARCHITECTURE.md # EDIT: note the new read-only admin consultation page (§ app table row)
```

The selector owns the query; the view stays thin. Read access crosses apps only through approved
means: the `DocumentVersion`/`EC` models are referenced by `"documents.DocumentVersion"` string keys
or read via model-level access inside `backlog` (matching the precedent in `pending_ecs()` and
`EC-Detail` reverse relations). Preview and download always route through `documents` views — this
page never touches uploaded file bytes directly.

## Database Schema Changes

**None.** No model, migration, or new stored field. The page reads fields already present on
`documents.DocumentVersion` (`version_number`, `file`, `uploaded_at`, `uploaded_by`, `change_reason`)
and `backlog.EC` (`ec_code`, `status`).

## Page Definition

**URL:** `/backlog/document-versions/` (route `backlog:document_versions`).

**Search:** optional `?q=` matches against EC code (`ec_code`), reference (`reference`), and version
number (`version_number`), case-insensitive, matching the search style of the EC list page.

**Ordering:** `uploaded_at` descending, stable tie-breaker on version `id`.

**Columns (Portuguese headers):**

| Header | Content |
|---|---|
| EC | `EC-<year>-<nnn>` linking to `backlog:ec_detail` |
| Versão | `version_number` badge (`v1.0`, `v1.1`, `v2.0`) |
| Enviado por | uploader full name (fallback username) |
| Enviado em | `dd/mm/yyyy hh:mm` |
| Motivo da alteração | `change_reason` (truncated, `—` when blank) |
| Acções | thumbnail (decision A), `Pré-visualizar` (modal), `Descarregar` |

**Preview modal:** one Bootstrap modal served by this page; each row's *Pré-visualizar* button loads
`documents:preview` for that version into an iframe inside the modal. The modal also holds the
`Descarregar` action for the same version. The modal is wired to the existing endpoint — no direct
file streaming from this page, so clickjacking (`xframe_options_sameorigin`), authentication, and
DOCX→PDF conversion behaviour are exactly those of the approved Issue #61 preview.

**Page size:** 25 rows, `django-tables2` pagination as on the audit-log and pending-EC pages.

**Empty state:** clear Portuguese message (`Ainda sem documentos.`) when the admin has versions but
the search returns nothing, or when the database has no versions at all.

**Non-goals:** no upload, no delete, no edit of `version_number`/`change_reason`, no status change,
no per-role dashboards for other roles. Other roles keep the EC detail page as their version view.

## Input / Output

**Input:** HTTP GET `/backlog/document-versions/`; optional `q` query param; optional page number.

**Access rules:**

| User | Result |
|---|---|
| Anonymous | 302 redirect to `LOGIN_URL` |
| Administrator | 200; all document versions, all ECs |
| Requester, CD, DES Team | 403; no version data returned |

(The Administrator-only rule matches the menu's placement in the Administrator sidebar block. If
reviewers prefer a wider read audience, this table is the single place to widen.)

**Thumbnail Behaviour (decision A only):**

- `static/vendor/pdfjs/` is vendored once (cherry-pick of the existing asset commit from the
  cancelled `feat/document-annotations` branch — identical bytes, no re-download).
- `document_thumbnails.js` fetches `documents:preview` for the row's version, renders page 1 onto a
  small `canvas` (same-origin, cookie-authorized), at a fixed thumbnail scale.
- Thumbnails lazy-load only when the row scrolls into view (`IntersectionObserver`), so a full page
  does not fetch 25 PDFs at once.
- Fallbacks, never a broken image: DOCX conversion failure (HTTP 422) → DOCX format icon; a version
  without a stored file → generic icon; non-viewer errors → neutral document icon.

## Edge Cases

1. No versions in the database → 200 with the empty state.
2. Search with no match → 200 with the empty state (not an error page).
3. A version whose file was lost/absent → row renders; *Pré-visualizar* and *Descarregar* are
   omitted for that row (mirrors the EC detail rule for missing files).
4. DOCX fails LibreOffice conversion → modal shows the existing Portuguese 422 message
   ("A pré-visualização não está disponível..."); download still works.
5. Legacy/imported rows keep their stored `version_number` strings (e.g. `v1.0`); the page never
   renumbers.
6. An EC with many versions yields one row per version — history is the point, no deduplication.
7. Preview modal is single-instance: opening another row's preview closes/replaces the previous
   one instead of stacking iframes.

## Acceptance Criteria

1. The `Versões de Documentos` sidebar item links to the new page (Administrator only).
2. Anonymous → login redirect; non-admin roles → 403.
3. Rows show EC link, version, uploader, timestamp, change reason, and the two read-only actions.
4. Newest upload first; `?q=` filters by EC code, reference, or version number.
5. Preview modal loads the existing `documents:preview` endpoint; download the original always
   works and never mutates the stored file.
6. Pagination and empty state work.
7. **Done:** feature tests + full suite pass; `uv run ruff check .` clean; no migration generated;
   no new Python dependency.

## Approved Decisions

1. **Branch:** `feat/document-versions-view`.
2. **Read-only scope:** consultation only; uploads/deletions stay in RF03/RF05 flows.
3. **Reuse:** preview modal and download use the existing `documents` endpoints; no new file bytes
   are streamed by this page.
4. **Page size:** 25 rows; EC list search style (`?q=`).

## Open Decisions (blocking spec approval)

1. **Thumbnails** — A: vendored PDF.js first-page canvas (recommended, no new system dependency;
   requires re-vendoring `static/vendor/pdfjs/` bytes); or B: format icons only (zero JS) — or a
   later C: server-side Poppler thumbnails (new system dependency, deferred).
2. **Access widening** — Administrator-only (matches sidebar placement) or Administrator + CD?
3. **Sidebar placement** — only replace the Administrator block's `#` link this round, or also
   surface the page for CD (which then needs the access rule from #2).
