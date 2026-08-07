# django-tourguide

Database-driven, multi-page guided tours for Django.

> ### 0.1.0: a first release
>
> Everything documented here works and is covered by tests. The version says what it says,
> though: this is the first release, and the JSON contract below is the part most likely to
> move. It is documented precisely for that reason, and a breaking change to it will be a major
> version like any other.

## What it does

Tours and their steps are ordinary Django models, so they are built and edited in the admin
rather than hardcoded. A tour can span several pages: each step records the page it belongs to,
and the tour navigates there and resumes when the user reaches it. Progress is stored per user
on the server, so a half-finished tour survives a reload, a new tab, or a different browser.

Rendering uses [driver.js](https://github.com/nilbuild/driver.js) (MIT, no runtime
dependencies), vendored into the package. Nothing about the models or endpoints is specific to
it: the server emits a JSON tour spec and a small adapter drives the renderer, so a different
renderer is a second adapter rather than a rewrite.

## Requirements

- Django 5.2, 6.0 or 6.1
- Python 3.10 to 3.14 on Django 5.2, or 3.12 to 3.14 on Django 6.x (Django 6.0 dropped the
  older Pythons)

CI tests both ends of each of those Python ranges, so the support claimed here is the support
that is actually exercised.

Django 4.2 and 5.1 are not supported: 5.1 reached end of life on 2025-12-03 and 4.2 on
2026-04-07.

## Install

```bash
pip install django-tourguide
```

Then add **both** apps to your settings:

```python
INSTALLED_APPS = [
    ...
    "tourguide",           # the tour definitions
    "tourguide.progress",  # per-user progress
]
```

They are two apps rather than one so that they can be placed separately under multitenancy
(below). In an ordinary project the split makes no difference, and you can otherwise ignore it.

Then mount the endpoints wherever you like:

```python
urlpatterns = [
    ...
    path("tourguide/", include("tourguide.urls")),
]
```

The prefix is yours to choose. Nothing in the package hardcodes it, so the client is told
where the endpoints live rather than assuming.

## Showing tours on your pages

Load the renderer once, in a base template:

```html
{% load tourguide %}
...
{% if user.is_authenticated %}{% tourguide %}{% endif %}
</body>
```

That emits driver.js, the adapter, both stylesheets, and the configuration the client needs.
Only signed-in users have tours, so there is nothing to load for anyone else.

By default a tour the user has never been offered opens by itself. Pass `{% tourguide
autostart=False %}` to load the renderer without offering anything, so tours only ever start
from a button. A half-finished tour still resumes either way: stopping partway and being
unable to continue is not a useful reading of "no autostart".

To let someone start a tour on purpose, for example to find it again after finishing it:

```html
{% tourguide_button "getting-started" "Take the tour again" %}
```

That is a convenience, not the mechanism. The client starts a tour from **any** element
carrying `data-tourguide-start="<slug>"`, so use your own markup and skip the tag if you would
rather:

```html
<a href="#" data-tourguide-start="getting-started" class="dropdown-item">Take the tour</a>
```

Asking for a tour restarts it from the beginning, including one already finished, which is the
point of asking again. If its first step is on another page, the browser goes there first.

### Tours that span pages

Each step records the page it belongs to, and the tour crosses between them on its own: when
the next step lives elsewhere, the adapter saves the position, navigates, and picks the tour up
on arrival. A step with no page of its own belongs to whatever page the tour is already on,
which is the usual case for consecutive steps.

Because the position is held on the server rather than in `sessionStorage`, a half-finished
tour survives a reload, a new tab, and a different browser. On load, a tour resumes only if the
step it stopped on belongs to the page the user is actually looking at, so it never navigates a
page somebody chose to open.

A step whose element is missing renders as a centred box and the tour carries on. That happens
legitimately (the step belongs to another page) and accidentally (a project restyled away the
thing it pointed at), and neither is worth breaking a tour over. An invalid selector is treated
the same way and logs a warning naming it.

### Themes

Out of the box a tour renders in driver.js's own look: a plain white card with small bordered
buttons. If your site is on Bootstrap, name it and the tour uses your buttons instead:

```python
TOURGUIDE_THEME = "bootstrap5"      # or "bootstrap3", "bootstrap4"
```

The setting is the normal place for it, since a project has one design system rather than one
per page. `{% tourguide theme="bootstrap3" %}` overrides it for a single template, which is for
the project part-way through changing frameworks with both in the tree at once.

**The theme applies your classes, it does not guess at your palette.** `btn btn-primary btn-sm`
and friends are Bootstrap's, already on the page, so the tour inherits whatever you compiled,
customisations included.

The popover box is the exception, because there is no framework class to borrow for it:
Bootstrap sizes `.popover` from variables declared inside that rule, and its `.popover-header`
cannot be lifted out of it. So the theme loads a small stylesheet that draws the box in the
metrics of the version you named: a titled header with a tint and a rule under it, that
version's padding and type scale, and the arrow tinted to match the edge it leaves from.

Bootstrap 5 gets a little more, because it is the only one of the three exposing variables its
own components consume: the box reads `--bs-body-bg` and friends, so a tour follows
`data-bs-theme="dark"` with no second stylesheet.

One thing you will notice: the close button shows Bootstrap's focus ring when a step opens.
driver.js focuses it deliberately, for keyboard users, and that ring is Bootstrap's own
affordance, the same one a modal's close button shows. It is left alone rather than styled
away, since removing it would take a focus indicator with it.

#### Your own design system

A theme is just a map of element to class, so a project that is not on Bootstrap describes its
own and needs nothing from this package:

```python
TOURGUIDE_THEME = "bulma"
TOURGUIDE_THEMES = {
    "bulma": {
        "popover": "box",
        "nextButton": "button is-primary is-small",
        "prevButton": "button is-small",
        "closeButton": "delete",
        "clearCloseLabel": True,       # the framework draws its own icon
    },
}
```

The same names may also replace a shipped theme, since project themes are looked up first. A
name that resolves to nothing is reported by `manage.py check` rather than quietly rendering
unstyled buttons, which looks identical to a theme that had no effect.

### Styling it yourself

`driver.css` already makes a tour legible, and `tourguide.css` adds only what the package needs
on top of it. Anything resembling a house style is deliberately left to you. Two class hooks
are part of the public interface and keep their names:

| | |
|---|---|
| `.tourguide-popover` | every step's popover, alongside driver.js's own classes |
| `.tourguide-button` | the button rendered by `{% tourguide_button %}` |

driver.js's own classes (`.driver-popover-title`, `-description`, `-footer`, `-next-btn`,
`-prev-btn`, `-close-btn`) are available too. Scope overrides under `.tourguide-popover` so
they apply to this package's tours and not to another driver.js on the same page.

With a theme in use the close button carries `.tourguide-close` rather than driver.js's
`-close-btn`: that class declares `all: unset`, which would beat a framework's button class in
the cascade, so it comes off and `.tourguide-close` puts back the positioning it was also
carrying.

driver.js 1.8.0 (MIT) is vendored into the app's static files, so there is no CDN and no build
step: run `collectstatic` and you are done.

## Shipping tour content

Tours live in the database so they can be edited, but they are also product content that ships
with a release. `loadtours` reconciles those two facts:

```bash
python manage.py loadtours getting-started      # a fixture inside an installed app
python manage.py loadtours path/to/tours.json   # or a path
```

A fixture is JSON, and only has to say what it cares about:

```json
{
  "tours": [
    {
      "slug": "quests",
      "name": "Quests",
      "audience": "staff",
      "steps": [
        {"order": 0, "title": "Your quests", "content": "<p>Everything you can work on.</p>",
         "element": "#quests-menu", "url_name": "quests:list"}
      ]
    }
  ]
}
```

Named fixtures are looked up in the `fixtures/tours/` directory of each installed app, the way
`loaddata` works, so a release carries its tours rather than a deployment step having to know
where they live.

**It is an upsert, not a load.** Tours match on slug and steps on order, so running it twice
changes nothing the second time, leaves primary keys alone, and never disturbs progress
records. Steps added to a fixture appear; steps removed from it go.

**A site's own edits are not thrown away.** Each import stamps the tour with a fingerprint of
what was written. On the next run, a tour whose content no longer matches its fingerprint has
been edited locally, and is left alone with a message saying so. `--force` overrides that. A
tour nobody imported is treated the same way, since it is somebody's own work either way.

```console
$ python manage.py loadtours getting-started
  skip     getting-started (edited since import, use --force to replace)
1 skipped
```

`--dry-run` reports what would change and writes nothing. The whole run is one transaction, so
a fixture that fails partway through leaves the database as it was rather than half-updated.

This is also what makes the shared-schema arrangement below practical: updating tour content
becomes one command run rather than a data migration for every tenant.

## Using it with django-tenants

The package does not depend on `django-tenants` and imports nothing from it, but it is built
so the two fit together well.

Tour content is usually product documentation: identical on every tenant, and written by
whoever maintains the application rather than by each tenant. So keep one copy of it in the
public schema and track progress per tenant:

```python
SHARED_APPS = (
    ...
    "tourguide",           # one copy of the tours, in the public schema
)

TENANT_APPS = (
    ...
    "tourguide.progress",  # per-user progress, in each tenant schema
)

# django-tenants still expects INSTALLED_APPS to be the union of the two, without duplicates.
INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]
```

Then migrate both halves:

```bash
python manage.py migrate_schemas --shared   # tour definitions, into the public schema
python manage.py migrate_schemas --tenant   # progress, into each tenant schema
```

This works because django-tenants composes `search_path` as `[tenant_schema, public]`, so a
table that exists only in `public` is still readable from a tenant request. The payoff is that
shipping a fix to a step's wording is a single update rather than a data migration across
every schema.

Two things to know:

- **Do not list `tourguide` in both `SHARED_APPS` and `TENANT_APPS`.** An app named in both
  gets its tables built in both, and the empty per-tenant copy would then shadow the populated
  public one.
- **Progress must stay tenant-side.** It foreign-keys the user model, and each tenant schema
  has its own users.

### Why progress refers to its tour by slug

`TourProgress` stores a tour slug rather than a `ForeignKey`. This is a deliberate design
choice, not a database restriction. PostgreSQL is perfectly capable of a constraint that
crosses schemas, and django-tenants puts `public` on the search path, so such a constraint can
even be created. What breaks is everything around it: a relation spanning the shared/tenant
boundary is not something django-tenants models, `migrate_schemas` runs per schema, and
deleting a shared `Tour` sends Django's deletion collector looking for related rows in tenant
tables it cannot see from the public context.

So the slug carries **no database constraint**, and referential integrity is the application's
concern instead. In practice that means a progress row can outlive the tour it names, and the
resolver returns nothing rather than raising when that happens.

That is the behaviour we want regardless of multitenancy: shipped tour content gets re-imported
whenever it is updated, and a real foreign key would cascade-delete everyone's progress each
time.

## The JSON contract

Three endpoints, mounted at whatever prefix you chose above. This is the seam that keeps the
renderer swappable: the server decides what a tour contains and who may see it, and a renderer
is whatever consumes this JSON.

Every response is JSON, including refusals. A tour runs on a page the user is already looking
at, so redirecting an unauthenticated caller to a login form would hand the client an HTML
document where it expected a spec. Anonymous callers get **403**, worded as JSON.

### `GET /` : the tours on offer

The active tours whose audience includes the current user, with that user's progress on each.

```json
{
  "tours": [
    {
      "slug": "quests",
      "name": "Quests",
      "description": "How quests work",
      "icon": "fa-scroll",
      "progress": {
        "last_step": 3,
        "started_at": "2026-08-06T20:12:40.512Z",
        "completed_at": null,
        "dismissed_at": null,
        "is_finished": false
      }
    }
  ]
}
```

`progress` is `null` when the user has never been offered the tour. That is **not** the same as
a record sitting at step zero: the absence of a record is what makes a tour start by itself, so
a client that conflates the two will re-offer tours people have already dismissed.

### `GET /<slug>/spec/` : one tour's steps

```json
{
  "slug": "quests",
  "name": "Quests",
  "description": "How quests work",
  "steps": [
    {
      "order": 0,
      "element": "#quests-menu",
      "title": "Your quests",
      "content": "<p>Everything you can work on lives here.</p>",
      "side": "bottom",
      "align": "start",
      "path": "/quests/"
    }
  ]
}
```

`path` is the page the step belongs to, already resolved: a step may name a Django route
rather than a literal path, and that name is reversed here because the client has no URLconf
to reverse against. It is `null` for a step that belongs to whatever page the tour is already
on, which is the usual case for consecutive steps.

`path` is also `null` if a step names a route that has since been renamed. That costs the step
its navigation but not its place in the tour, and logs a warning naming the tour and the route.
The alternative, failing the request, would take down a whole tour over one step, and the host
project can rename a route at any time with nothing written to this package's tables.

### `POST /<slug>/progress/` : record where the user got to

```json
{"action": "step", "step": 3}
{"action": "completed"}
{"action": "dismissed"}
```

Responds with `{"slug": ..., "progress": {...}}` carrying the stored record. Posting repeatedly
for one tour updates the single record rather than accumulating rows, `step` only ever moves
forward, and completion and dismissal keep their original timestamps if repeated.

Completion and dismissal are recorded separately. Both stop a tour reappearing, but collapsing
them would lose the difference between a tour people finish and one everybody abandons, which
is the main thing worth knowing about a tour.

This endpoint is **not CSRF-exempt**: send `X-CSRFToken` as you would for any Django POST. The
write is small but real, since a forged request could mark a tour dismissed so that it never
appears for that user again.

### The audience gate

Every endpoint enforces the audience server-side, not just the picker. Requesting a staff-only
tour's spec, or posting progress for it, as a user outside that audience returns **404** rather
than 403, worded identically to a slug that names no tour at all. A 403 would confirm to
someone who guessed a slug that a tour by that name exists, which turns the endpoint into a way
to enumerate the staff-facing parts of your site.

## Demo project

`demo/` is a real, runnable single-tenant Django site used to develop and screenshot the
package:

```bash
pip install -e .
python demo/manage.py migrate
python demo/manage.py runserver
```

It has two pages, which is what a multi-page tour needs to demonstrate navigation and resume.

Seed a tour that crosses between them, plus a user to view it as:

```bash
python demo/manage.py demotour     # imports the tour and creates user 'demo' (password 'demo')
```

That imports `demosite/fixtures/tours/getting-started.json` through `loadtours`, which is how
a real project ships tour content, and creates a user to view it as.

Sign in at `/admin/login/`, then open `/`. The tour starts by itself, crosses to Settings
partway through, and resumes there if you reload mid-tour.

## Development

```bash
pip install -e .
python -m django test tests --settings=tests.settings
ruff check .
```

Note that `--settings` has to come *after* the subcommand: `django-admin` reads `argv[1]` as
the command name, so `python -m django --settings=... test` fails with "Unknown command".
Exporting `DJANGO_SETTINGS_MODULE=tests.settings` works too.

### How pull requests get merged

Pull requests merge themselves. The `Auto-merge` workflow arms GitHub's auto-merge on every
pull request raised from a branch in this repository, and GitHub then squash-merges it as soon
as everything `main` requires is satisfied.

Two repository settings have to be in place for that, and the workflow does nothing useful
without either:

- **Settings → General → Pull Requests → Allow auto-merge**, which is what permits auto-merge
  to be armed at all.
- **A ruleset on `main` requiring the `ci-ok` status check**, which is what a merge then waits
  for.

A third is optional but wanted, and its absence is quiet rather than obvious:

- **An `AUTO_MERGE_TOKEN` secret**, holding a fine-grained personal access token scoped to this
  repository with *contents: read and write* and *pull requests: read and write*.

  Whoever arms auto-merge is who GitHub records as merging, and that identity decides whether
  `Closes #123` closes anything: GitHub does **not** close linked issues when the merge is
  attributed to `github-actions[bot]`, which is the built-in `GITHUB_TOKEN`'s identity. With
  the secret set, the merge is attributed to a person and GitHub closes them itself. Without
  it, everything still merges and linked issues simply have to be closed by hand, which the
  workflow warns about on every run.

  A workflow reacting to the merge cannot substitute for it. GitHub creates no workflow run at
  all from an event that `GITHUB_TOKEN` triggered, so a `pull_request_target: closed` job never
  fires for these merges.

  The token spends its owner's API quota, shared with everything else that account does, so it
  can be rate limited for reasons that have nothing to do with the repository. The workflow
  arms with the built-in token when that happens, so the pull request still merges and only the
  issue-closing is lost, and it says so.

What a merge actually waits on is the ruleset on `main`, not that workflow. The ruleset
requires one status check, `ci-ok`, which is a job in `CI` that succeeds only if `lint`, every
`test` matrix job, and `demo` all succeeded. Requiring that one name rather than the eight
underlying jobs keeps the ruleset stable when the matrix changes, and means a job renamed on a
branch fails the check instead of quietly dropping out of it.

Two things are deliberately left alone. Pull requests from forks are never armed, because the
review here is automated and auto-merging one could land outside code with nobody having read
it. And the ruleset does not require branches to be up to date before merging, since these
pull requests are stacked: with that on, every merge would invalidate the next pull request in
the stack and force a full re-run.

GitHub refuses to arm auto-merge whenever it has nothing left to hold a merge for, which it
reports as "clean status". That happens for two opposite reasons, so the workflow decides
between them on the evidence rather than assuming:

- **The checks have already passed**, which is normal on a pull request taken out of draft, or
  reopened, after CI has finished. There is nothing to wait for because the waiting is over, so
  the workflow merges it.
- **Nothing was ever required**, because the ruleset is missing. Merging here would land code
  that was never checked, so the workflow warns and leaves the pull request to be merged by
  hand.

It tells the two apart by asking whether `ci-ok` itself passed on the head commit. Reading the
ruleset would answer that more directly, but a workflow cannot: the built-in token cannot be
granted administration scope, so rulesets are not readable from CI at all.

### Cutting a release

A release is a tag. `Release` builds and publishes on any `v*` tag, and nothing else triggers
it, so publishing is always something someone chose to do.

1. Bump the version in `pyproject.toml` **and** `tourguide/__init__.py`. A test asserts the two
   agree, so forgetting one fails CI rather than shipping a package whose `__version__` lies.
2. Add the release to `CHANGELOG.md`.
3. Merge that, then tag the merge commit `vX.Y.Z` and push the tag.

The workflow refuses a tag that disagrees with the packaged version, before building anything:
the tag is what a release page, a changelog heading and a pinned `pip install` all read the
version off, and PyPI does not allow taking a version back.

Uploading uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), so there is no
token in this repository at all: each run exchanges a short-lived OpenID Connect identity for
an upload credential that expires with it. PyPI is told once which workflow may publish, which
means **renaming `release.yml` breaks publishing** until the publisher is updated to match.
Setting that up on a project that does not exist on PyPI yet is a *pending publisher*, under
Your account → Publishing:

| | |
|---|---|
| PyPI project name | `django-tourguide` |
| Owner | `bytedeck` |
| Repository | `django-tourguide` |
| Workflow | `release.yml` |
| Environment | `pypi` |

## Why not an existing package

- [`django-tours`](https://github.com/wilmerm/django-tours) is the closest fit and has a good
  model shape, but its `url_names` is a filter for which pages a tour appears on, not per-step
  navigation, so tours cannot span pages. It also tracks only whether a user has seen a tour,
  not where they got to, and it hangs a user many-to-many off the tour table, which rules out
  keeping definitions in a shared schema.
- [`django-tour`](https://github.com/ambitioninc/django-tour) is a mandatory-workflow gate
  ("require the user to complete a series of steps"), not a UI tour. Last released 2015.
- [`django-driverjs`](https://github.com/iwalucas/django-driverjs) is a thin driver.js wrapper
  at 0.1.x with no models.

The Bootstrap-popover tour libraries (`bootstrap-tour`, `bootstrap-tourist`) are all
unmaintained and none supports Bootstrap 5, which is why this package renders through a
framework-agnostic engine and leaves styling to a stylesheet.

## License

MIT
