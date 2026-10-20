# Spec — Document Versions Page (`Versões de Documentos`)

**Status:** SPEC_APPROVED (2026-11-10) — the page reshaped from a version-row table into an
EC-chip list plus a per-EC thumbnail gallery, confirmed with the user; implementation follows on
`feat/document-versions-view` in one-commit-per-step order.

## Objective

Give the Administrator a dedicated, read-only way to browse document versions across all ECs,
replacing the `#` placeholder behind `Versões de Documentos` in the Administrator sidebar, and a
visual gallery to see at a glance how each document evolved.

Two pages, one flow:

1. **List page** — a grid of clickable EC chips (one chip per EC that owns at least one document
   version). A chip shows the EC code as a button-like label, the EC reference, and the version
   count. Clicking a chip opens that EC's gallery.
2. **Gallery page** — for the chosen EC, one card per document version, newest first. Each card
   shows a first-page thumbnail rendered in the browser, the version badge, uploader and timestamp,
   and the two read-only actions: inline preview (modal) and original download.

The pages write nothing: uploading, deleting, and version numbering stay with the existing RF03
(create EC with document) and RF05 (re-upload new version) flows, and `workflow` keeps owning every
status change.

This feature is derived from RF05 (automatic versioning / version history), RF06 (attached
document), RF12 (consultation), RNF01 (role-based access), and RNF05 (usability). The SRD does not
describe an admin-wide document-versions view; this spec proposes it as the read-only consultation
view the sidebar item has always promised.

## Tech Stack

Django 6.1, existing `DocumentVersion`, `EC`, and `User` models, the existing `documents:preview` /
`documents:download` endpoints, Bootstrap 5 grid components for the chips/cards (plain templates,
`django-tables2` is **not** used here), and vendored **PDF.js 4.10.38** static assets for
thumbnails. **No new Python dependency, no CDN.**

## Commands

```bash
uv run pytest apps/documents/tests/test_document_versions_view.py  # feature tests
uv run pytest                                                      # full suite
uv run ruff check .                                                # lint
uv run python manage.py runserver                                  # manual check as Administrator
```

## System Architecture

```
apps/documents/
├── selectors.py   # add version_ecs(q=None) and ec_versions(ec_pk); document_versions() removed
├── views.py       # EDIT: DocumentVersionsListView rewritten for chips;
│                  #       add ECVersionsGalleryView (login + Administrator check)
├── urls.py        # add /documents/document-versions/<int:ec_pk>/ (name: ec_versions)
└── tests/
    └── test_document_versions_view.py  # EDIT: rewritten for chips + gallery
                                        #       (access, chip data, search, gallery order,
                                        #        thumbnail markers, fallbacks)

templates/documents/
├── document_versions.html   # EDIT: rewrite — chips grid + search + empty state
└── ec_versions_gallery.html # NEW: gallery page (header, cards, preview modal, back link)

static/js/
└── document_thumbnails.js   # NEW: lazy first-page thumbnails via vendored PDF.js

static/vendor/pdfjs/          # NEW: cherry-pick of PDF.js assets from the cancelled
├── pdf.min.mjs               #        feat/document-annotations branch (same bytes,
└── pdf.worker.min.mjs        #        no re-download)

apps/documents/tables.py      # DELETE on this branch: the version-row table is replaced by chips

templates/base.html           # EDIT: replace the `Versões de Documentos` `#` link with the
                              #       documents:document_versions named route
docs/ARCHITECTURE.md          # EDIT: keep the app-table row in sync with the new shape
```

The selector owns the query; the view stays thin. All logic lives inside the `documents` app, so
the dependency direction (`workflow → documents → backlog → accounts`) is never crossed. Preview
and download always route through the existing `documents` views — nothing on these pages touches
uploaded file bytes directly. `EC` chips reference the EC only through the template URL tags; no
`backlog` import is needed in Python.

## Database Schema Changes

**None.** No model, migration, or new stored field. The pages read fields already present on
`documents.DocumentVersion` (`version_number`, `file`, `uploaded_at`, `uploaded_by`, `change_reason`)
and `backlog.EC` (`year`, `number_sequence`, `reference`, `status`).

## Page Definition

### List page — EC chips

**URL:** `/documents/document-versions/` (route `documents:document_versions`).

**Search:** optional `?q=` narrows the chips; it matches the EC code (parsed from
`EC-<year>-<nnn>` into `year` + `number_sequence`, since `ec_code` is a computed property, not a
stored column) or the EC reference (`reference`), case-insensitive.

**Chip population rule:** only ECs with **at least one** `DocumentVersion`. ECs without documents
do not render a chip at all — the page is about documents.

**Chip ordering:** by each EC's newest upload (`uploaded_at` descending), so recently touched
documents surface first.

**Chip content (single card, Bootstrap grid):**

- Button-like label: `EC-<year>-<nnn>`.
- Small line: EC reference.
- Small line: version count (e.g. `2 versões`).

**Gallery link target:** `documents:ec_versions` for that EC (not `backlog:ec_detail`).

**Pagination:** none in this first version; the chip count stays small next to the EC universe and
the `?q=` search covers navigation. Revisit if it grows.

**Empty state:** Portuguese message (`Ainda sem documentos.`) when the database has no versions at
all, or the search matches no EC.

### Gallery page — per-EC version cards

**URL:** `/documents/document-versions/<int:ec_pk>/` (route `documents:ec_versions`).

**Header:** EC code + reference + status badge, a `Voltar` link to the list page, and
*Ver EC completa* linking to `backlog:ec_detail` for the full EC context.

**Card ordering:** versions newest first (`uploaded_at` descending, stable `id` tie-breaker).

**Card content (per `DocumentVersion`):**

- Thumbnail: first page of the document, rendered client-side (see Thumbnail Behaviour).
- Version badge: `v1.0` / `v1.1` / `v2.0` — stored strings, never renumbered.
- Small line: uploader full name (fallback username) and `dd/mm/yyyy hh:mm`.
- Actions: `Pré-visualizar` (modal) and `Descarregar` (original).

**Preview modal:** one Bootstrap modal on the gallery page; each card's *Pré-visualizar* button
loads `documents:preview` for that version into the modal iframe. The modal footer holds the
`Descarregar` action for the same version. The modal is wired to the existing endpoint — no direct
file streaming from these pages, so clickjacking (`xframe_options_sameorigin`), authentication,
and DOCX→PDF conversion behaviour are exactly those of the approved Issue #61 preview.

**Pagination:** none in the gallery; an EC's version chain is short by design (v1.0, v1.1, v2.0).

## Input / Output

**Input:** HTTP GET on either URL; the list page accepts an optional `q` query param.

**Access rules (both pages):**

| User | Result |
|---|---|
| Anonymous | 302 redirect to `LOGIN_URL` |
| Administrator | 200 |
| Requester, CD, DES Team | 403; no version data returned |

The Administrator-only rule matches the menu's placement in the Administrator sidebar block; if a
wider read audience is ever wanted, this table is the single place to widen.

**Thumbnail Behaviour (active, PDF.js approved):**

- `static/vendor/pdfjs/` is vendored once (cherry-pick of the existing asset commit from the
  cancelled `feat/document-annotations` branch — identical bytes, no re-download).
- `document_thumbnails.js` fetches `documents:preview` for the card's version, renders page 1 onto
  a small `canvas` (same-origin, cookie-authorized) at a fixed thumbnail scale.
- Thumbnails lazy-load only when the card scrolls into view (`IntersectionObserver`), so the
  gallery never fetches every PDF at once.
- Fallbacks, never a broken image: DOCX conversion failure (HTTP 422) → DOCX format icon; a version
  without a stored file → generic icon; any other viewer error → neutral document icon.

## Edge Cases

1. No versions in the database → list page renders 200 with the empty state.
2. Search with no match → 200 with the empty state (not an error page).
3. Gallery URL for an EC without versions (or a nonexistent EC) → 404; chips only ever point to
   ECs that own documents, but a hand-typed URL must fail safely.
4. A version whose file was lost/absent → its card renders with the generic icon and no
   *Pré-visualizar*/*Descarregar* action (mirrors the EC detail rule for missing files).
5. DOCX fails LibreOffice conversion → its card shows the DOCX icon; if the user forces
   *Pré-visualizar*, the modal shows the existing Portuguese 422 message
   ("A pré-visualização não está disponível..."), and download still works.
6. Legacy/imported rows keep their stored `version_number` strings (e.g. `vMP1.0` as imported);
   the page never renumbers.
7. Preview modal is single-instance: opening another card's preview replaces the previous iframe
   target instead of stacking iframes.

## Acceptance Criteria

1. The `Versões de Documentos` sidebar item links to the list page (Administrator only); both
   pages share the Administrator-only access rule.
2. The list shows one clickable chip per EC with at least one document version; `?q=` narrows the
   chips; no chip appears for ECs without documents.
3. Clicking a chip opens the gallery page with that EC's versions newest first.
4. Each card renders a lazy first-page thumbnail through vendored PDF.js, or a fallback icon when
   no file / conversion failure applies.
5. The preview modal loads the existing `documents:preview` endpoint; download of the original
   always works and never mutates the stored file.
6. Empty state, 404 safety, and the single-modal rule work.
7. **Done:** feature tests + full suite pass; `uv run ruff check .` clean; no migration generated;
   no new Python dependency; `apps/documents/tables.py` removed with this branch.

## Approved Decisions

1. **Branch:** `feat/document-versions-view`.
2. **Shape:** EC-chip list (`document_versions`) + per-EC thumbnail gallery (`ec_versions`);
   rows-per-version table is removed.
3. **Read-only scope:** consultation only; uploads/deletions stay in RF03/RF05 flows.
4. **Reuse:** preview modal and download use the existing `documents` endpoints; no new file bytes
   are streamed by these pages.
5. **Access:** Administrator-only on both pages, matching the sidebar placement.
6. **Thumbnails:** vendored PDF.js 4.10.38 first-page render, lazy-loaded, with icon fallbacks.
7. **Chip population:** only ECs with at least one document version.
8. **Tooling:** plain Bootstrap grid instead of `django-tables2` on these two pages; no pagination
   in this first version (search covers the list page; the gallery is short by design).
