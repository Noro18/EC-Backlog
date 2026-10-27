# Spec — Inline PDF Preview on EC Detail (`Preview de PDF`)

**Status:** SPEC_APPROVED (revised scope includes DOCX preview and the Issue #37 access decision).

## Objective

Implement Issue #61: when a user opens an EC detail page, show the **latest PDF document version**
inline in the page rather than requiring the user to open/download it separately.

- PDF: show an embedded, browser-readable preview for the latest `DocumentVersion` only.
- DOCX: convert the latest original DOCX to a PDF preview on the server and show that PDF inline.
  The original DOCX remains unchanged and downloadable in its original format.
- Other unsupported file types: do not try to convert or embed them; retain a usable download/open
  link and show a clear Portuguese fallback message.
- EC with no attached file: show neither an empty viewer nor a broken link.
- Older document versions remain available through the existing version-history links; this feature
  does not embed every version.
- No annotation, editing, document comparison, or rewriting/replacing the uploaded original.

This feature supports RF05 (version history), RF06 (document upload), RNF01 (access control), and
RNF05 (usability). It does not change upload validation or document-version behavior.

## Blocking Decision — Issue #37

**Decision: Option B.** Preview and download require an authenticated session. Any authenticated
application role that can open the current EC detail page may preview/download the EC's documents;
anonymous users may not. This matches `ECDetailView` (`LoginRequiredMixin`) and does not introduce
new per-role restrictions.

Both preview and original-file downloads must use the protected document endpoint. Remove or replace
the development `/media/` route in `config/urls.py` so it cannot bypass authentication. Production
media serving must likewise route through the protected policy rather than exposing raw file URLs.

## Tech Stack

Django 6.1, existing `DocumentVersion.file` (`FileField`), a browser PDF viewer, and LibreOffice in
headless mode to convert DOCX files to PDF. LibreOffice is a server-side system executable, not a
Python package managed by `uv`; it must be installed in each runtime environment that performs
preview conversion. No model or database dependency is added.

## Commands

```bash
uv run pytest apps/backlog/tests/test_ec_detail_preview.py  # feature tests
uv run pytest                                              # full suite
uv run ruff check .                                        # lint
uv run python manage.py runserver                          # manual browser check
```

## System Architecture

Common UI changes:

```
apps/backlog/
├── views.py   # expose the latest DocumentVersion for the detail page
└── tests/
    └── test_ec_detail_preview.py  # NEW: PDF, DOCX, unsupported, and no-file behavior

templates/backlog/ec_detail.html  # EDIT: inline latest PDF; preserve download links/fallbacks

apps/documents/
├── services.py  # add DOCX-to-PDF conversion using LibreOffice headless; keep original unchanged
├── views.py     # NEW: authenticated preview/original-download endpoint
├── urls.py      # NEW: authenticated document endpoint
└── tests/       # add preview/access tests and conversion tests with converter mocked

config/urls.py   # EDIT: include documents URLs and remove the public development media route
```

The EC detail view already prefetches `versions` and `versions__review`; use the prefetched
versions to identify the latest version (the model orders versions newest first). Keep view logic
thin and do not import `DocumentVersion` into `backlog`; follow the existing reverse relation from
`EC` (`ec.versions`).

The conversion service must produce a temporary PDF derivative for preview and must not replace the
uploaded DOCX or write a new `DocumentVersion`. Do not add a database field or persist a second
version. Set a bounded conversion timeout and clean up temporary output after serving it. If
conversion fails or times out, the EC detail page remains usable, the original DOCX download stays
available, and a Portuguese message explains that preview is unavailable.

All file links on the EC detail page, including older-version downloads, must use this authenticated
endpoint. Do not leave raw `DocumentVersion.file.url` links that bypass the login check.

## Database Schema Changes

**None.** No model changes, migrations, or new stored fields. The preview reads the latest existing
`DocumentVersion.file`; any DOCX-derived PDF is temporary and is not stored as a new document version.

## Input / Output

**Input:** GET an existing EC detail URL. The latest `DocumentVersion` is selected using the
existing version ordering (`-id`).

| Latest document | Expected output |
|---|---|
| PDF exists | Authenticated inline viewer displays the latest PDF; the original PDF remains available to download. |
| DOCX exists and conversion succeeds | Inline viewer displays its temporary PDF derivative; download still returns the original DOCX. |
| DOCX exists and conversion fails | No broken viewer; original DOCX download remains, with a Portuguese preview-unavailable message. |
| Unsupported non-PDF exists | No conversion/viewer; existing download/open link and Portuguese explanation are shown. |
| No document version or no file | No viewer and no file link; existing empty-document message remains. |

All versions remain in the existing history list with their current links. The preview is only for
the latest version.

## Edge Cases

1. No versions → do not render an empty `<iframe>`, `<embed>`, or object tag.
2. Latest version is DOCX → convert only that version; never replace or rename the original.
3. DOCX conversion fails, the converter is unavailable, or conversion times out → graceful fallback,
   original download remains available, and no empty/broken viewer appears.
4. An older version is PDF but the latest version is DOCX → preview the latest DOCX conversion, not
   the older PDF.
5. Unsupported non-PDF → no conversion attempt; retain download/open link.
6. Missing file value → treat like no attached file, with no broken URL.
7. An anonymous request for either preview or original download is redirected to login.
8. Preview markup is lazy-loaded below the fold to limit page weight.

## Acceptance Criteria

1. Opening an EC with a latest PDF displays that PDF inline without requiring a download action.
2. A latest DOCX is converted for inline preview while its download link continues to return the
   original DOCX unchanged.
3. An EC without a document shows no empty viewer or broken link.
4. Only the latest version is embedded; previous versions remain accessible through history links.
5. Conversion failure/timeout shows a friendly fallback and preserves original download.
6. All authenticated roles who can view EC detail may preview and download; anonymous users may not.
   Raw `/media/` URLs cannot bypass this check in development or production.
7. Tests cover PDF, DOCX conversion, conversion failure, unsupported file, no-file, and latest-version
   behavior.
8. No model/migration changes; tests and `ruff check .` pass.

## Runtime Requirement

Install LibreOffice headless in the runtime environment where DOCX previews are generated. The
repository currently has no Dockerfile or deployment image definition; document the local/server
installation requirement as part of implementation notes. Tests must mock the converter executable
so the Python test suite does not require LibreOffice to be installed.
