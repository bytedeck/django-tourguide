# django-tourguide

Database-driven, multi-page guided tours for Django.

Tours and their steps are ordinary Django models, so they are built and edited in the admin
rather than hardcoded. A tour can span several pages: each step records the page it belongs
to, and the tour navigates there and resumes when the user moves on to it. Progress is stored
per user on the server, so a half-finished tour survives a reload, a new tab, or a different
browser.

Rendering uses [driver.js](https://github.com/nilbuild/driver.js) (MIT, no runtime
dependencies), vendored into the package. Nothing about the models or endpoints is specific to
it: the server emits a JSON tour spec and a small adapter drives the renderer, so a different
renderer is a second adapter rather than a rewrite.

> **Status: pre-release.** The models, endpoints, and renderer land across
> [#2](https://github.com/bytedeck/django-tourguide/issues/2) through
> [#8](https://github.com/bytedeck/django-tourguide/issues/8). This README describes install
> and layout; the authoring and theming guides arrive with the features they document.

## Requirements

- Python 3.10+
- Django 4.2+

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
```

This works because django-tenants composes `search_path` as `[tenant_schema, public]`, so a
table that exists only in `public` is still readable from a tenant request. The payoff is that
shipping a fix to a step's wording is a single update rather than a data migration across
every schema.

Two things to know:

- **Do not list `tourguide` in both.** An app named in both lists gets its tables built in
  both, and the empty per-tenant copy would then shadow the populated public one.
- **Progress must stay tenant-side.** It foreign-keys the user model, and each tenant schema
  has its own users. For the same reason `TourProgress` refers to its tour by slug rather than
  by foreign key, since a cross-schema foreign key is not possible. That turns out to be the
  right call regardless: re-importing shipped content would otherwise cascade-delete
  everyone's progress.

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
python -m django test tests   # with DJANGO_SETTINGS_MODULE=tests.settings
ruff check .
```

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
