"""Views for the demo project.

Both pages are the same view: a template, plus the one piece of state the demo needs.
"""

from django.views.generic import TemplateView


class DemoPage(TemplateView):
    """A demo page that remembers which Bootstrap the visitor asked for.

    The choice arrives as `?bs=5`, but a tour crossing to the other page navigates to a plain
    path, and the query string does not survive that. Keeping it in the session means the theme
    holds for the whole tour rather than vanishing at the very step worth showing off.

    A host project would have one design system and no switch at all, so this is demo
    furniture rather than anything the package expects.
    """

    def get(self, request, *args, **kwargs):
        """Latch a `?bs=` choice into the session before rendering."""
        if "bs" in request.GET:
            request.session["bs"] = request.GET["bs"]
            request.session["dark"] = "dark" in request.GET
        return super().get(request, *args, **kwargs)
