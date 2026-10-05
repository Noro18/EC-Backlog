# Spec: New EC Form (create an EC)

## Objective

`GET|POST /backlog/new_ec/` creates one Configuration Specification (EC) from a form and lists it in the
backlog.

- As an authenticated requester, I fill in the reference, description, a release and a CD, and
  submit; the system assigns the **EC ID itself** (RF01) instead of asking me to type it.
- As an authenticated requester, I attach a document if I have one (RF06) and it is stored as
  version `v1.0` with my name on it.
- As an authenticated requester, I land on the EC list with a success message and my new EC
  in it, showing `year-sequence` (e.g. `2026-001`).
- As an anonymous visitor I am sent to the login page — a form that writes data is not public.
- As a CD or DES user I do **not** get the button, and a crafted POST still gets **403**;
  only `requester` and `administrator` may create (agreed 2026-10-05).
- As an attacker who crafts a POST, I **cannot** put an EC into a full or closed release: the
  server re-checks capacity. A `<option disabled>` in the HTML is a courtesy, not a rule.

**Why this exists — SRD mapping.** RF01 (automatic EC ID), RF02 (associate with an open
Release, one-to-many), RF03 (creation date), RF06 (document upload), RF07 (assign a CD).
This is `RELEASE_MODULE.md` Deferred item 1: the **write side** of the selector/service
pattern, where `backlog/services.py` gets its first practice.

**Out of scope:** RF08 (email), RF09/RF10 (review and decision — `workflow`), RF05 (version
increment on resubmission — a later `documents` slice), RF04 (go-live — `workflow`, DES role),
RF12 (filters), user/role CRUD, editing or deleting an existing EC. This slice **creates** and
nothing else.

## Assumptions

1. **Auth and role gate.** The form writes, so anonymous access stops at the login page
   (`LoginRequiredMixin`, `LOGIN_URL = "accounts:login"` already configured). Among
   authenticated users only `requester` and `administrator` may create an EC — agreed
   2026-10-05 — and everyone else (CD, DES) gets **403**, not a redirect. `requester` is
   always taken from `request.user`, never from POST data.
2. **EC year = year of submission** (agreed 2026-10-05): `timezone.localdate().year`,
   numbered per calendar year per RF01 — *not* the release's year. An EC filed in 2027
   against a 2026 release is `2027-001`. Annex A is entirely 2026, so the two readings
   were indistinguishable until this decision.
3. `creation_date` (RF03) is set to today, not typed by the user — SRD §6 step 3 says it is
   recorded "at the moment of submission". No date input on the form.
4. `status` stays at the model default `in_validation` and `is_imported` at `False`; this
   slice **never assigns them** (ARCHITECTURE § status changes go through `workflow` only).
5. The release dropdown lists only releases that are **open and have room**; full and closed
   ones are not offered at all.
6. The document field is **optional** — an EC without a document is a valid submission.

## Decisions (agreed 2026-10-05)

1. **Django `ModelForm`** in a new `apps/backlog/forms.py`, template renders `{{ form }}`.
   The current hand-written inputs (`name="reference"` etc.) are replaced — validation, CSRF,
   `required` and error display come from Django instead of being hand-built in a fat view.
2. **The upload happens in this slice**, which needs `backlog` to call a `documents` service.
   `ARCHITECTURE.md:96` forbids that outright ("Never import upward"), so a **documented
   narrow exception** is recorded there instead of the rule being broken silently. It adds
   one edge to the graph; `documents` still imports only `core`, so no cycle appears.
3. **CD assignment is a plain FK write** at creation time (the template already asks for it).
   RF07's *decisions* stay in `workflow`; storing who was assigned is not a status transition.
4. **After success: EC list + message.** `/backlog/detail_ec/<pk>/` still renders a static
   template with no context, so redirecting there would land the user on an empty page. A
   `{% if messages %}` block is added to `base.html` (the app already installs
   `django.contrib.messages` but renders it nowhere).
5. **Numbering is `Max(number_sequence) + 1`, never `count() + 1`.** Annex A has real gaps
   (`1,2,3,6,7`) and ARCHITECTURE requires new IDs never to collide with imported history —
   `count()+1` would mint a duplicate `2026-004`.
6. **`reference` uniqueness is form-level only.** The model has no unique constraint, so this
   slice adds no migration; a DB constraint is a separate, ask-first change.
7. **Role gate: `requester` + `administrator`, enforced in the view — and hiding is not the
   gate.** Agreed 2026-10-05. A role test in the view returns **403** for CD/DES on both GET
   and POST; anonymous still redirects to login. `base.html:33` already wraps "Nova
   Solicitação" in `{% if user.role == 'requester' %}` — so today the *display* is restricted
   while the *write* is wide open to anyone with DevTools or `curl`, which is the wrong way
   round. This slice closes the view gate (the authoritative half, required by
   ARCHITECTURE:121 — "enforce permissions in views and services, not only in templates")
   and widens that sidebar condition to include `administrator`, since the admin block at
   `base.html:59` currently offers no link to the form the user is now allowed to use.

## Tech Stack

Django 6.1, Bootstrap 5 + Inter. **No new dependencies** — file validators already exist in
`apps/documents/validators.py` and `MEDIA_ROOT` is configured.

## Commands

```bash
uv run pytest apps/backlog/tests/ -q        # form, service and selector tests
uv run pytest                               # full suite (currently 63 green)
uv run ruff check . && uv run ruff format apps/backlog/
uv run python manage.py runserver           # manual: sidebar → "Nova Solicitação"
```

## Project Structure

```
apps/backlog/
├── forms.py            # NEW — ECCreateForm(ModelForm)
├── services.py         # NEW — next_ec_number(year), create_ec(...)
├── selectors.py        # + open_releases_with_ec_count()
├── views.py            # NewECView → CreateView, LoginRequiredMixin, form_valid
├── urls.py             # unchanged: new_ec/ name="ec_form"
└── tests/
    ├── test_services.py   # NEW — numbering + capacity
    ├── test_views.py      # + TestNewECForm
    └── factories.py       # existing ReleaseFactory / ECFactory
apps/documents/
└── services.py         # NEW — create_first_version(ec, uploaded_by, file)
templates/
├── backlog/ec_form.html   # render {{ form }}, keep the cards and the "ATENÇÃO" note
└── base.html              # + messages block (success/error), + administrator on the
                           #   "Nova Solicitação" condition (Decision 7)
```

## Code Style

The service owns the rules; the view only orchestrates (ARCHITECTURE § thin views):

```python
# apps/backlog/services.py
def next_ec_number(year: int) -> int:
    """Max(number_sequence) + 1 for this calendar year — gaps are never reused."""
    ...

def create_ec(*, requester, reference, description, release, responsible_cd) -> EC:
    """Create one EC inside a transaction, re-checking capacity against a locked row."""
    with transaction.atomic():
        fresh = Release.objects.select_for_update().get(pk=release.pk)
        if fresh.ecs.count() >= fresh.capacity:
            raise ValidationError("Release lotada — selecione outra release.")
        ...
```

```python
# apps/backlog/views.py
class NewECView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = ECCreateForm
    template_name = "backlog/ec_form.html"
    success_url = reverse_lazy("backlog:ec_list")

    # Do NOT set raise_exception = True. Both mixins share AccessMixin.raise_exception,
    # so it would also turn the anonymous visitor's login redirect into a 403 (test 7).
    # Defaults give exactly the split we want:
    #   anonymous          → redirect to LOGIN_URL
    #   logged-in, wrong role → handle_no_permission() raises PermissionDenied → 403

    def test_func(self):
        return self.request.user.role in (
            User.Role.REQUESTER,
            User.Role.ADMINISTRATOR,    # never a raw "cd" string literal
        )

    def form_valid(self, form):
        with transaction.atomic():
            ec = create_ec(requester=self.request.user, **form.cleaned_data)
            if file := self.request.FILES.get("document"):
                create_first_version(ec=ec, uploaded_by=self.request.user, file=file)
        messages.success(self.request, f"EC {ec.ec_code} criada com sucesso.")
        return super().form_valid(form)
```

`test_func` runs for GET **and** POST, so the gate cannot be skipped by posting directly.
Order matters: `LoginRequiredMixin` first, so the login check runs before the role check.
The sidebar condition is the courtesy layer only:

```django
{% if user.role == 'requester' or user.role == 'administrator' %}
  <li class="nav-item"><a href="{% url "backlog:ec_form" %}" ...>Nova Solicitação</a></li>
{% endif %}
```

The selector fixes the two queries-per-release that `ec_form.html:35,37` currently pays
(`{{ r.ecs.count }}` **and** `{{ r.is_full }}` both hit the DB):

```python
# apps/backlog/selectors.py
def open_releases_with_ec_count():
    """Open releases with a free seat, annotated — one query, no N+1 in the dropdown."""
    return (
        Release.objects.filter(is_open=True)
        .annotate(ec_total=Count("ecs"))
        .filter(ec_total__lt=F("capacity"))
        .order_by("-year", "-number_sequence")
    )
```

The template keeps its cards and labels but drops the hand-written inputs, and uses the
model's `full_name` property instead of `get_full_name` (which returns `" "` for a user with
no names, so `|default:` never fires and the option renders as `()`):

```django
<label class="form-label">Selecionar Release <span class="text-danger">*</span></label>
{{ form.release }}
```

## Testing Strategy

pytest-django + factory-boy, written **before** the code per
`.opencode/skills/django-tdd-loop/SKILL.md`. Numbering and capacity live in
`test_services.py` (a service is not a view); form behaviour lives in
`TestNewECForm` in `test_views.py`.

Status key: ⏳ all pending — this spec is not yet approved.

**`test_services.py`**

1. ⏳ `next_ec_number()` on an empty year returns `1`.
2. ⏳ Existing sequences `1, 2, 3, 6` → next is **`7`** (the gap is skipped, never reused).
3. ⏳ `create_ec()` sets `requester`, `year`, `number_sequence` and `creation_date`, and
   leaves `status`/`is_imported` at their model defaults.
4. ⏳ Against a capacity-10 release, the **11th** EC is refused (ARCHITECTURE's sequential
   capacity test — SQLite cannot test the concurrent variant).
5. ⏳ Capacity is re-checked **inside** the service: a caller that skipped the form's
   `disabled` option still cannot exceed capacity.
6. ⏳ A closed release (`is_open=False`) refuses new ECs.

**Role gate — `test_views.py`**

7. ⏳ Anonymous `GET /backlog/new_ec/` → redirect to `accounts:login`.
8. ⏳ A **CD** `GET` → **403** (and the same for a DES user).
9. ⏳ A **CD** `POST` of an otherwise valid form → **403** with **no** EC created — the test
   that proves the sidebar `{% if %}` is not the permission check.
10. ⏳ An **administrator** `GET` → 200, and a `POST` → EC created (grant is symmetric).
11. ⏳ The sidebar renders "Nova Solicitação" for `requester` and `administrator` and hides it
    from CD.

**`test_views.py::TestNewECForm`**

12. ⏳ `GET /backlog/new_ec/` while logged in as a requester → 200, `form` in the context.
13. ⏳ Valid POST → an EC exists with `ec_code` `2026-001`, `requester` = the logged-in user,
    `creation_date` = today; redirect to `ec_list`; the success message is **rendered**.
14. ⏳ Valid POST with a file → a `DocumentVersion` `v1.0` exists for that EC, with
    `uploaded_by` set (the first caller of the documented exception).
15. ⏳ Blank `description` → 200, a form error, and **no** EC created.
16. ⏳ An `.exe` upload → rejected, no `DocumentVersion` (the validators are on the model).
17. ⏳ POST targeting a full release → refused from the HTTP side, no EC (test 5's twin).
18. ⏳ Two consecutive POSTs → `2026-001`, then `2026-002`.
19. ⏳ **No N+1 in the dropdown:** query count constant as the release count grows — this is
    the test that fails if `open_releases_with_ec_count()` is replaced with the raw loop.
20. ⏳ Closed and full releases are absent from `form.fields["release"].queryset`.

## Boundaries

- **Always:** TDD (red → green), `uv run pytest` + ruff before done, writes in `services.py`,
  thin views, `LoginRequiredMixin` + `UserPassesTestMixin` (defaults, no `raise_exception`),
  `transaction.atomic()` around the create, the numbering service called with no view-side
  arithmetic, roles compared through the `User.Role` enum.
- **Ask first:** model or migration changes (a `reference` uniqueness constraint needs one),
  new dependencies, filtering, touching `workflow`.
- **Never:** assign `EC.status` here (it stays at the model default; transitions belong to
  `workflow`), use `count()+1` to mint an EC ID, import `documents` from anywhere other than
  the single `form_valid` call site named by the `ARCHITECTURE.md` exception, treat the
  form's `disabled` `<option>` as capacity enforcement, or **treat a sidebar `{% if %}` as the
  permission check** — hiding a link authorizes nobody.

## Success Criteria

- The sidebar's "Nova Solicitação" link leads to a form that actually creates an EC, and the
  new EC appears on `/backlog/ec/` with `year-sequence` generated, never typed.
- A CD or DES user gets **403** on GET *and* on a crafted POST — no EC is created — even
  though the button is hidden from them anyway.
- An administrator sees the button and can create; an anonymous visitor goes to login.
- Posting a full or closed release from a crafted request creates nothing.
- The 11th EC against capacity 10 is refused by the service, not by the HTML.
- The dropdown makes a constant number of queries as releases grow.
- An optional upload lands as `DocumentVersion` `v1.0`; the rest of the form works with no file.
- The success message is visible after the redirect.
- New tests pass, the existing 63 stay green, `ruff check` + `ruff format` clean.

## Deferred

- `create_release()` / `next_release_number()` — RF02 also allows *creating* a release, but
  this form only offers an existing one. Its own slice.
- `documents` reupload with version increment (RF05, `v1.1`, `v2.0` + `change_reason`).
- Email notification on assignment (RF08) — `workflow`.
- Reference uniqueness as a DB constraint — needs a decision, therefore a migration.
- **Found and already fixed by PR #24 (not this slice):** `base.html:45` tested
  `user.role == 'CD'` while the enum value is lowercase `'cd'`. Noted here because it is the
  reason raw string literals for roles appear in the Never list.

## Open Questions

None — both resolved 2026-10-05:

1. **EC year vs release year** → **submission year** (Assumption 2).
2. **Who may create** → **`requester` + `administrator`**, 403 for everyone else
   (Assumption 1, Decision 7).
