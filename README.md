# django-tourguide

Database-driven, multi-page guided tours for Django.

> ### Pre-release: not usable yet
>
> **What exists today:** an installable package containing two empty Django apps, a runnable
> demo project, a test suite, and CI. There are no models, no endpoints, and no renderer, so
> there is nothing to author a tour with and nothing to run.
>
> Everything described below is the plan, landing across
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
