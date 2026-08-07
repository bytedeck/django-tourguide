# Changelog

Notable changes, newest first. Versions follow [semantic versioning](https://semver.org/), and
the JSON contract in the README is part of the public interface: a breaking change to it is a
major version, the same as a breaking change to the Python API.

## [0.1.0] - 2026-08-07

First release.

### Added

- **Tours as models.** `Tour` and `Step` are ordinary Django models, edited in the admin rather
  than hardcoded, so tour content is changed without a deploy.
- **Tours that span pages.** Each step records the page it belongs to. Reaching a step on
  another page saves the position, navigates, and picks the tour up there.
- **Progress on the server, per user.** A half-finished tour survives a reload, a new tab and a
  different browser. Finished and abandoned are recorded separately, so a tour someone
  dismissed is not offered again while an unfinished one resumes.
- **`{% tourguide %}` and `{% tourguide_button %}`**, the whole template-side interface: one
  tag in a base template runs tours on every page, and the other renders a control that starts
  a named tour, navigating first if it begins elsewhere.
- **`loadtours`**, which imports tours from JSON by fixture name or path, so tour content ships
  with a release like any other product content while staying editable afterwards.
- **A documented JSON contract.** The three endpoints are specified in the README precisely
  enough to write a second renderer against, and nothing server-side is specific to driver.js.
- **driver.js 1.8.0 vendored** (MIT, no runtime dependencies), so there is no CDN and no build
  step: run `collectstatic` and it works.
- **Bootstrap 3, 4 and 5 themes.** A theme applies the host project's own button classes, and
  draws the popover in that version's own metrics: a titled header with its tint and rule, that
  version's padding and type scale, and the arrow tinted to the edge it leaves from. Bootstrap
  5 reads `--bs-*` variables, so a tour follows `data-bs-theme="dark"` on its own. A project on
  another design system describes its own theme in settings without touching this package.
- **django-tenants support.** The package is two apps so a deck's tour definitions can live in
  a shared schema while progress stays per tenant. Progress refers to its tour by slug rather
  than by foreign key, which is what makes that split possible.

[0.1.0]: https://github.com/bytedeck/django-tourguide/releases/tag/v0.1.0
