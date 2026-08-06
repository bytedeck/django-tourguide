"""Template tags for loading the renderer and offering a tour.

Two tags, and between them they are the whole public template API:

``{% tourguide %}``
    Emits the stylesheets, the scripts, and the configuration the client needs. Put it once
    per page, usually in a base template.

``{% tourguide_button "slug" %}``
    Renders a button that starts a named tour.
"""

from django import template
from django.core.exceptions import ImproperlyConfigured
from django.middleware.csrf import get_token
from django.urls import NoReverseMatch, reverse

register = template.Library()

#: Stand-in slug used to build a URL pattern the client fills in for itself.
#:
#: The endpoints take a slug, but the client needs the shape of the URL rather than one
#: instance of it, and where they are mounted is the host project's choice. So each is
#: reversed once with this placeholder and the client substitutes the real slug. It has to be
#: a valid slug for ``reverse`` to accept it, which rules out anything more obviously inert.
SLUG_PLACEHOLDER = "__tourguide_slug__"


@register.inclusion_tag("tourguide/loader.html", takes_context=True)
def tourguide(context, autostart=True):
    """Load the tour renderer on this page.

    Pass ``autostart=False`` to load the renderer without offering anything by itself, so
    tours only ever start from a button. An in-flight tour still resumes either way: stopping
    halfway through and being unable to continue is not a useful reading of "no autostart".
    """
    request = context.get("request")
    return {
        "config": {
            "endpoints": {
                "list": _reverse("tourguide:tour-list"),
                "spec": _reverse("tourguide:tour-spec", SLUG_PLACEHOLDER),
                "progress": _reverse("tourguide:tour-progress", SLUG_PLACEHOLDER),
            },
            "slugPlaceholder": SLUG_PLACEHOLDER,
            "autostart": bool(autostart),
            # Read here rather than from the cookie, so the progress endpoint still works
            # under CSRF_USE_SESSIONS, where there is no cookie to read.
            "csrfToken": get_token(request) if request is not None else "",
        }
    }


@register.inclusion_tag("tourguide/button.html")
def tourguide_button(slug, label="Take the tour", css_class="tourguide-button"):
    """Render a button that starts the tour named by ``slug``.

    This is a convenience, not the mechanism: the client starts a tour from any element
    carrying ``data-tourguide-start="<slug>"``, so a project that wants its own markup can
    put that attribute on whatever it likes and skip this tag.
    """
    return {"slug": slug, "label": label, "css_class": css_class}


def _reverse(name, *args):
    """Reverse one of the package's URL names, explaining the fix if it is not mounted.

    ``NoReverseMatch`` here means the host project has loaded the app but not included
    ``tourguide.urls``, which is easy to miss and produces a puzzling failure inside a
    template otherwise.
    """
    try:
        return reverse(name, args=args)
    except NoReverseMatch as error:
        raise ImproperlyConfigured(
            "django-tourguide could not reverse '%s'. Add its URLs to your URLconf, "
            "for example: path('tourguide/', include('tourguide.urls'))." % name
        ) from error
