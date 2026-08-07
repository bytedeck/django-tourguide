"""Themes: what classes to hang on the popover so it matches the surrounding site.

A theme is **data, not code**. It is resolved here and shipped to the client in the config,
and the adapter simply applies what it is handed. That keeps the adapter free of any knowledge
of Bootstrap, which is the same property that makes the renderer swappable, and it means a
project can describe its own design system in settings without touching this package.

The classes named here are not defined by this package. They are the host project's, already
loaded on the page, so a themed tour inherits whatever that project compiled, customisations
and all. Anything the classes cannot express lives in ``tourguide-themes.css``.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

#: Setting naming the theme to use, or ``None`` for driver.js's own plain look.
SETTING = "TOURGUIDE_THEME"

#: Classes this package puts on elements it needs to position itself.
#:
#: The close button is the only one: a theme takes driver.js's class off it, to stop
#: ``all: unset`` fighting the framework's own button styling, and that class carried the
#: absolute positioning. This one carries the positioning and nothing else.
CLOSE_CLASS = "tourguide-close"

#: driver.js classes a theme removes before applying its own.
#:
#: ``.driver-popover-footer-btn`` declares ``all: unset`` and then rebuilds a small bordered
#: button. Because ``{% tourguide %}`` emits driver.css after the project's own stylesheets,
#: that rule wins the cascade against any framework button class of equal specificity, so the
#: framework's class has to be applied in its absence rather than alongside it.
#:
#: Nothing functional depends on either: driver.js binds its handlers to element references,
#: and the disabled state uses ``.driver-popover-btn-disabled``, scoped under
#: ``.driver-popover-footer``, which still matches.
REPLACED_CLASSES = {
    "buttons": "driver-popover-footer-btn",
    "close": "driver-popover-close-btn",
}

#: Marks a popover as Bootstrap-shaped, whichever version it is.
#:
#: driver.js renders no header and sizes the popover with numbers of its own, so the shipped
#: stylesheet has to draw a Bootstrap-looking box. The three versions differ only in their
#: metrics, so the shape is written once against this class and each version restates the
#: handful of values it sizes differently.
SHARED_CLASS = "tourguide-bootstrap"

BOOTSTRAP3 = {
    "popover": f"{SHARED_CLASS} tourguide-bootstrap3",
    "nextButton": "btn btn-primary btn-sm",
    "prevButton": "btn btn-default btn-sm",
    "closeButton": "close",
    # Bootstrap 3's `.close` styles a glyph the markup supplies, and driver.js already puts a
    # multiplication sign there, so it is left alone.
    "clearCloseLabel": False,
}

BOOTSTRAP4 = {
    **BOOTSTRAP3,
    "popover": f"{SHARED_CLASS} tourguide-bootstrap4",
    # `btn-default` was dropped in Bootstrap 4.
    "prevButton": "btn btn-secondary btn-sm",
}

BOOTSTRAP5 = {
    **BOOTSTRAP4,
    "popover": f"{SHARED_CLASS} tourguide-bootstrap5",
    # `.close` became `.btn-close` in Bootstrap 5, and it draws its own icon with a
    # background image rather than styling a supplied glyph.
    "closeButton": "btn-close",
    # So driver.js's multiplication sign has to go, or the button shows two.
    "clearCloseLabel": True,
}

#: The themes this package ships.
THEMES = {
    "bootstrap3": BOOTSTRAP3,
    "bootstrap4": BOOTSTRAP4,
    "bootstrap5": BOOTSTRAP5,
}

#: Keys a theme may set. A project defining its own is checked against this, so a typo is
#: reported rather than silently ignored by the adapter.
THEME_KEYS = set(BOOTSTRAP5)


def get_theme(name=None):
    """Return the class map for ``name``, falling back to the setting, or ``None``.

    ``None`` means no theme, which is the default and leaves the markup exactly as driver.js
    renders it.

    A name that is not a shipped theme is looked up in ``TOURGUIDE_THEMES``, so a project can
    describe its own design system in settings. That is why an unknown name raises rather than
    quietly rendering unstyled: silently ignoring it would look like the theme simply had no
    effect, which is a slow thing to debug.
    """
    name = name if name is not None else getattr(settings, SETTING, None)
    if not name:
        return None

    custom = getattr(settings, "TOURGUIDE_THEMES", {})
    if name in custom:
        return _validated(name, custom[name])
    if name in THEMES:
        return THEMES[name]

    raise ImproperlyConfigured(
        f"Unknown tourguide theme '{name}'. Available: {', '.join(sorted(THEMES))}. "
        f"Define your own by adding it to a TOURGUIDE_THEMES dict in settings."
    )


def _validated(name, theme):
    """Check a project-defined theme, naming the offending key rather than failing later."""
    if not isinstance(theme, dict):
        raise ImproperlyConfigured(f"TOURGUIDE_THEMES['{name}'] should be a dict of classes, not {type(theme).__name__}.")

    unknown = set(theme) - THEME_KEYS
    if unknown:
        raise ImproperlyConfigured(
            f"TOURGUIDE_THEMES['{name}'] has unknown keys: {', '.join(sorted(unknown))}. Allowed: {', '.join(sorted(THEME_KEYS))}."
        )
    return theme
