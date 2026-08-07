"""System checks, so a misconfigured theme is reported rather than discovered.

A theme that does not resolve produces markup with no framework classes on it, which looks
like a theme that simply had no effect. That is a slow thing to debug from the browser, and
`manage.py check` is where Django expects to tell you instead.
"""

from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured

from tourguide.themes import SETTING, get_theme


@register()
def check_theme(app_configs, **kwargs):
    """Confirm the configured theme resolves, if one is configured at all."""
    if not getattr(settings, SETTING, None):
        return []

    try:
        get_theme()
    except ImproperlyConfigured as error:
        return [
            Error(
                str(error),
                hint=f"Set {SETTING} to a shipped theme, or add your own to TOURGUIDE_THEMES.",
                id="tourguide.E001",
            )
        ]
    return []
