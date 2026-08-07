# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

django-tourguide is a reusable Django app providing database-driven, multi-page guided tours.
Tours and their steps are ordinary models, so they are authored in the admin rather than
hardcoded; the server emits a JSON spec and a small adapter drives [driver.js](https://github.com/nilbuild/driver.js),
which is vendored into the package. Progress is stored per user on the server, so a
half-finished tour survives a reload, a new tab, or a different browser.

The package is deliberately **standalone**. It has no dependency on any particular host
project, and nothing in it should acquire one. It ships as two apps so they can be placed
separately under multitenancy: `tourguide` (the definitions) and `tourguide.progress` (per-user
progress). It does **not** depend on or import `django-tenants`, and must not start: the
multitenant arrangement is a documented recipe, not a coupling.

The main branch is `main`. Python 3.10+ and Django 5.2+.

## Development Commands

```bash
pip install -e .
python -m django test tests --settings=tests.settings
ruff check .
```

`--settings` has to come **after** the subcommand: `django-admin` reads `argv[1]` as the
command name, so `python -m django --settings=... test` fails with "Unknown command".
Exporting `DJANGO_SETTINGS_MODULE=tests.settings` works too.

### Coverage

```bash
coverage run --source=src -m django test tests --settings=tests.settings
coverage report -m
```

### The demo project

`demo/` is a real, runnable single-tenant Django site used to develop and screenshot the
package. Verifying a front-end change here is not optional (see below).

```bash
pip install -e .
python demo/manage.py migrate
python demo/manage.py demotour        # imports the tour, creates user 'demo' (password 'demo')
python demo/manage.py runserver
```

## Architecture

* `src/tourguide/` holds `Tour` and `Step`, the authoring admin, the JSON endpoints, the
  template tags, and the vendored renderer. It is the shared half under multitenancy.
* `src/tourguide/progress/` holds `TourProgress` only. It foreign-keys the user model, so it is
  the per-tenant half.
* **Progress refers to its tour by slug, never by `ForeignKey`.** That is what lets the two
  halves live in different schemas, and it is right regardless: `loadtours` re-imports shipped
  content, and a real foreign key would cascade-delete everyone's progress each time. The cost
  is that a progress row can outlive the tour it names, so the resolver returns `None` rather
  than raising.
* **The JSON contract is the seam.** The server decides what a tour contains and who may see
  it; the adapter draws it. A second renderer should be a second adapter, not a rewrite, so
  nothing outside `tourguide.js` may know driver.js exists.
* **Audience gating is enforced server-side on every endpoint**, by calling
  `Tour.is_visible_to()` rather than reimplementing it as a query filter. A tour the user may
  not see returns **404, not 403**, worded identically to a slug that names nothing, so the
  endpoint cannot be used to enumerate what a site's staff-facing features are called.

## Code Style

* Ruff (lint only, no formatter) with `line-length = 150`; migrations excluded. Config lives in
  `pyproject.toml`. Use `select` rather than `extend-select`, so the rule set is what the file
  says rather than whatever ruff's defaults happen to be in a given release.
* Test naming: `test_method_or_class_name__specific_case_being_tested`, e.g.
  `test_record_step__does_not_rewind()`. All tests need a useful docstring.
* Bug fixes must be test-driven: include a test that fails without the fix.
* New code is expected to be **100% covered**. Code that genuinely cannot be exercised gets an
  inline `# pragma: no cover` **with a short comment saying why**, never to dodge a test that
  could reasonably be written.
* All methods and classes need docstrings; non-trivial code needs comments explaining **why**.
* **Comments must describe the code as it is now, never the code that was removed.** No
  "instead of…", "no longer…", "used to…", "rather than the old X". Once the PR merges that
  history is gone and the comment refers to context a future reader cannot see. Put the
  narrative in the PR description or commit message.
* **No em dashes, anywhere.** Not in user-facing copy, docs, PR descriptions, comments, or
  commit messages. Use a colon for a substatement, or (brackets) for a parenthetical aside.
* Prefer `model.full_clean()` before `model.save()` in new code.

## PR Conventions

* **Prefix every commit message and PR title with the type of change**: one of `feat`, `fix`,
  `chore`, `style`, `refactor`, `docs`, `perf`, `test`, `ci`, followed by a colon and a space
  ([Conventional Commits](https://www.conventionalcommits.org/)). E.g.
  `fix: merge an already-eligible pull request instead of warning about it`.
* Reference issues where applicable ("Closes #123").
* Claude Code: **open PRs by default, don't ask.** Opening a PR is the expected, reversible
  default. Exceptions: the user said not to, or the work is a throwaway spike.
* Claude Code: **keep moving through a plan.** Advance to the next step as soon as the previous
  step's PR is **merged**. Still stop for genuine blockers or ambiguity needing a decision.
* Claude Code: **always watch the PRs you own.** Any time you open a PR, or push to a branch
  with an open PR, subscribe with `subscribe_pr_activity` and stay subscribed until it is
  merged or closed. Because webhooks do not cover everything (CI success, new pushes,
  merge-conflict transitions), schedule a periodic self check-in (e.g. `send_later`).
* Claude Code: **keep the PR description canonical.** Whenever you change a PR in response to
  review, update the body to match. It should describe what will be merged, not what it looked
  like when first opened.
* Claude Code: after addressing a review comment, **mark the thread resolved**
  (`resolve_review_thread`) rather than leaving it dangling.
* Claude Code: sign everything you post to GitHub with "- Claude Code (`<session-name>`)",
  using the session's human-readable name.
* Claude Code: **clean up after merges.** Once a PR you own is merged, `git fetch --prune` and
  `git branch -D <branch>`. The remote head branch is deleted automatically. Do **not** try to
  `git push origin --delete`: the hosted environment's git proxy blocks it. Never touch the
  `pr-assets` branch.

### Merging

Pull requests merge themselves. The `Auto-merge` workflow arms GitHub's auto-merge on every PR
raised from a branch in this repository, and GitHub squash-merges once everything `main`
requires is satisfied. What gates a merge is the **ruleset on `main`** (which requires the
`ci-ok` status check), not the workflow. Two repository settings have to be in place:
`Settings → General → Pull Requests → Allow auto-merge`, and that ruleset.

`ci-ok` is a single aggregate check that passes only if `lint`, every `test` matrix job, and
`demo` passed. Requiring that one name rather than the eight underlying jobs keeps the ruleset
stable when the matrix changes.

A third setting, the `AUTO_MERGE_TOKEN` secret, decides whether `Closes #123` works, and this
repository has it: **linked issues close on merge by themselves, so do not close them by
hand.** Doing it anyway is not harmless, since it attributes the close to you rather than to
the pull request that earned it.

The secret is what puts a person's identity on the merge. GitHub does not close linked issues
when the merge is attributed to `github-actions[bot]`, which is what the built-in token is,
and no workflow can pick up the slack: GitHub creates no workflow run at all from an event
that `GITHUB_TOKEN` triggered. So if an `Auto-merge` run ever warns that the secret is
missing, it has lapsed or been removed: close that pull request's issues by hand, and say so
rather than leaving it looking like it worked.

### CodeRabbit

The automated review runs with `request_changes_workflow: true`, so it submits a **Request
changes** review while it has open findings and **Approves** once they are resolved. Its
approval satisfies the branch-protection review requirement.

Treat its findings as review comments to clear, not a hard wall: act on the good ones (push the
fix, then resolve the thread), and reply on the ones you are declining with a short reason
(then resolve). Its walkthrough and summary comments are informational.

**Its review quota is a rolling one shared across PRs, not a per-PR cooldown.** A window quoted
on one PR does not mean another PR's review is available, and reviewing one PR consumes the
slot the next was waiting for. If it posts a rate-limit notice instead of reviewing, schedule a
reminder past the stated window and only then post `@coderabbitai review`. Firing early just
re-hits the limit.

## Verifying front-end changes

Anything that changes what a user sees or does must be **verified in the running demo project**,
not only in tests. The JavaScript is not covered by `coverage`, and the behaviours that matter
most (multi-page navigation, resume after reload, a step whose element is missing) only appear
in a browser.

Drive the demo at `127.0.0.1:8011` with a real browser and check the actual behaviour. Screenshots
for a PR must come from that running demo: mockups and hand-built HTML are not acceptable, since
they do not prove the change works and routinely diverge from what really renders.

### Embedding screenshots in a PR

GitHub does not render `data:` URIs or arbitrary external images in PR markdown, and headless
sessions have no attachment-upload API. Commit images to the dedicated **`pr-assets`** branch
and reference them by raw URL:

```
![alt](https://raw.githubusercontent.com/bytedeck/django-tourguide/pr-assets/<issue>/<name>.png)
```

`pr-assets` is an **orphan, image-only branch** with no shared history with `main`. It is never
merged and never deleted, and is exempt from the post-merge branch cleanup above. Add to it with
a throwaway index so your working branch is untouched:

```bash
git fetch origin +refs/heads/pr-assets:refs/remotes/origin/pr-assets
export GIT_INDEX_FILE=$(mktemp -u)
git read-tree origin/pr-assets
B=$(git hash-object -w path/to/shot.png)
git update-index --add --cacheinfo 100644,$B,<issue>/shot.png
TREE=$(git write-tree); unset GIT_INDEX_FILE
C=$(git commit-tree $TREE -p origin/pr-assets -m "Add PR screenshots: ...")
git push origin $C:refs/heads/pr-assets
```

Fetch with an explicit refspec as shown. `git fetch origin pr-assets` updates only `FETCH_HEAD`,
leaving `origin/pr-assets` stale, and committing onto a stale parent is rejected as a
non-fast-forward.
