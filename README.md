# django-tourguide

Database-driven, multi-page guided tours for Django.

> ### Pre-release: not usable yet
>
> **What exists today:** the models, the admin used to author a tour, and the JSON endpoints
> described below, plus a runnable demo project, a test suite, and CI. There is no renderer
> yet, so a tour can be built and its spec fetched, but nothing draws it on a page.
>
> The rest is the plan, landing across
> [#2](https://github.com/bytedeck/django-tourguide/issues/2) through
> [#8](https://github.com/bytedeck/django-tourguide/issues/8). Installing it now gets you two
> app entries in `INSTALLED_APPS` and nothing else. This banner comes off at 0.1.0.

## What it will do

Tours and their steps will be ordinary Django models, so they are built and edited in the
admin rather than hardcoded. A tour will be able to span several pages: each step records the
page it belongs to, and the tour navigates there and resumes when the user reaches it.
Progress will be stored per user on the server, so a half-finished tour survives a reload, a
new tab, or a different browser.

Rendering will use [driver.js](https://github.com/nilbuild/driver.js) (MIT, no runtime
dependencies), vendored into the package. Nothing about the models or endpoints will be
specific to it: the server emits a JSON tour spec and a small adapter drives the renderer, so
a different renderer is a second adapter rather than a rewrite.

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

## Development

```bash
pip install -e .
python -m django test tests --settings=tests.settings
ruff check .
```

Note that `--settings` has to come *after* the subcommand: `django-admin` reads `argv[1]` as
the command name, so `python -m django --settings=... test` fails with "Unknown command".
Exporting `DJANGO_SETTINGS_MODULE=tests.settings` works too.

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
