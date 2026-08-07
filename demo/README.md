# Demo project

A real, runnable single-tenant Django site, used to develop and screenshot the package.

```bash
pip install -e .
python demo/manage.py migrate
python demo/manage.py demotour        # imports the tour, creates user 'demo' (password 'demo')
python demo/manage.py runserver
```

Sign in at `/admin/login/` as `demo` / `demo`, then open `/`. The tour starts by itself,
crosses to Settings partway through, and resumes there if you reload mid-tour.

## Trying the Bootstrap themes

The demo can load a real Bootstrap and the matching tour theme, which is how the themes are
checked against the actual frameworks rather than against a guess at them:

| | |
|---|---|
| `/?bs=3` | Bootstrap 3 |
| `/?bs=4` | Bootstrap 4 |
| `/?bs=5` | Bootstrap 5 |
| `/?bs=5&dark` | Bootstrap 5 in dark mode, which the theme follows on its own |
| `/` | no framework, driver.js's own plain look |

Those stylesheets are **not** in this repository, since three CSS frameworks is a lot of weight
for a demo. Fetch them once:

```bash
mkdir -p demo/demosite/static/vendor
for v in 3.4.1:3 4.6.2:4 5.3.3:5; do
  ver="${v%%:*}"; major="${v##*:}"
  curl -sL "https://registry.npmjs.org/bootstrap/-/bootstrap-$ver.tgz" | \
    tar -xzO package/dist/css/bootstrap.min.css > "demo/demosite/static/vendor/bootstrap$major.min.css"
done
```

Without them the page renders unstyled and everything still works, which is rather the point:
a theme is the host project's own classes, not stylesheets this package ships.

The choice is remembered in the session rather than read from the query string each time, so it
survives the tour navigating to the other page. A host project has one design system and no
switch at all; this is demo furniture.

## Re-recording the README GIF

The animation at the top of the main README is captured from this site by `record_gif.py`,
which needs `playwright` and `pillow`:

```bash
pip install playwright pillow && playwright install chromium
python demo/manage.py runserver 127.0.0.1:8011
python demo/record_gif.py tour.gif
```

It walks the tour and screenshots as it goes, so every frame is the real app. Re-record it
whenever a change alters what a tour looks like, and see `CLAUDE.md` for where the file goes
and why the README's URL carries a `?v=`.
