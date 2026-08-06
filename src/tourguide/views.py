"""JSON endpoints for listing tours, fetching one tour's spec, and recording progress.

This is the seam that keeps the renderer swappable. The server decides what a tour contains
and who is allowed to see it; the client receives plain JSON and draws it. A second renderer
implements this contract rather than reaching into the models.

Every outcome is JSON, including refusals. A tour is driven by a fetch from a page the user is
already looking at, so redirecting an unauthenticated caller to a login page, which is what
``login_required`` does, would hand the client an HTML document where it expected a spec.
"""

import json
import logging
from functools import wraps

from django.http import JsonResponse
from django.urls import NoReverseMatch
from django.views.decorators.http import require_GET, require_POST

from .models import Tour
from .progress.models import TourProgress

logger = logging.getLogger(__name__)

#: The values accepted in a progress request's ``action`` field.
PROGRESS_ACTIONS = ("step", "completed", "dismissed")


def json_login_required(view):
    """Refuse anonymous callers with JSON instead of redirecting them to a login page.

    The refusal is 403 rather than 401 because 401 obliges the response to carry a
    ``WWW-Authenticate`` header naming a challenge scheme, and session authentication has no
    scheme to name.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"detail": "Authentication required."}, status=403)
        return view(request, *args, **kwargs)

    return wrapper


@require_GET
@json_login_required
def tour_list(request):
    """Return the tours this user may be offered, with their progress on each."""
    tours = [tour for tour in Tour.objects.all() if tour.is_visible_to(request.user)]
    progress_by_slug = {
        progress.tour_slug: progress
        for progress in TourProgress.objects.filter(user=request.user, tour_slug__in=[tour.slug for tour in tours])
    }
    return JsonResponse(
        {
            "tours": [
                {
                    "slug": tour.slug,
                    "name": tour.name,
                    "description": tour.description,
                    "icon": tour.icon,
                    "progress": _progress_payload(progress_by_slug.get(tour.slug)),
                }
                for tour in tours
            ]
        }
    )


@require_GET
@json_login_required
def tour_spec(request, slug):
    """Return the ordered steps of one tour, ready for the renderer to run."""
    tour = _visible_tour(request.user, slug)
    if tour is None:
        return _no_such_tour(slug)

    return JsonResponse(
        {
            "slug": tour.slug,
            "name": tour.name,
            "description": tour.description,
            "steps": [_step_payload(step, tour.slug) for step in tour.steps.all()],
        }
    )


@require_POST
@json_login_required
def record_progress(request, slug):
    """Record how far this user got, or that they finished or gave up.

    Not CSRF-exempt. The writes here are small but real: a forged request could mark someone's
    tour dismissed so it never appears again. Callers send ``X-CSRFToken`` like any other POST.
    """
    tour = _visible_tour(request.user, slug)
    if tour is None:
        return _no_such_tour(slug)

    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Expected a JSON body."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Expected a JSON object."}, status=400)

    # Validated in full before anything is written, because creating the record is itself a
    # meaningful act: a tour starts by itself only while the user has no progress record for
    # it, so a record created while serving a request that then failed would quietly stop the
    # tour ever being offered.
    action = payload.get("action")
    if action not in PROGRESS_ACTIONS:
        return JsonResponse({"detail": f"'action' must be one of: {', '.join(PROGRESS_ACTIONS)}."}, status=400)

    step_order = payload.get("step")
    if action == "step" and not _is_step_order(step_order):
        return JsonResponse({"detail": "'step' must be a non-negative integer."}, status=400)

    progress, _ = TourProgress.objects.get_or_create(user=request.user, tour_slug=tour.slug)
    if action == "step":
        progress.record_step(step_order)
    elif action == "completed":
        progress.mark_completed()
    else:
        progress.mark_dismissed()

    return JsonResponse({"slug": tour.slug, "progress": _progress_payload(progress)})


def _visible_tour(user, slug):
    """Return the tour named by ``slug`` if ``user`` may see it, otherwise ``None``.

    The audience test is :meth:`Tour.is_visible_to` rather than a query filter written here,
    so there is exactly one definition of who may see a tour. It already covers inactive
    tours, so this does not filter on ``is_active`` as well.
    """
    tour = Tour.objects.filter(slug=slug).first()
    if tour is None or not tour.is_visible_to(user):
        return None
    return tour


def _no_such_tour(slug):
    """Refuse a tour this user may not see.

    404 rather than 403, and worded identically whether the tour is missing or merely
    forbidden. A 403 would confirm to a student who guessed a slug that a staff-only tour by
    that name exists, turning the endpoint into a way to enumerate what the staff-facing parts
    of the site are called.
    """
    return JsonResponse({"detail": f"No tour '{slug}' is available."}, status=404)


def _progress_payload(progress):
    """Serialise one progress record, or ``None`` if the user has no record for the tour.

    ``None`` is not the same as a record sitting at step zero. The absence of a record is what
    makes a tour start by itself, so the client has to be able to tell the two apart.
    """
    if progress is None:
        return None
    return {
        "last_step": progress.last_step,
        "started_at": progress.started_at.isoformat(),
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
        "dismissed_at": progress.dismissed_at.isoformat() if progress.dismissed_at else None,
        "is_finished": progress.is_finished,
    }


def _step_payload(step, tour_slug):
    """Serialise one step, with its page already resolved to a path."""
    return {
        "order": step.order,
        "element": step.element,
        "title": step.title,
        "content": step.content,
        "side": step.side,
        "align": step.align,
        "path": _step_path(step, tour_slug),
    }


def _step_path(step, tour_slug):
    """Resolve the page a step lives on, tolerating a URL name that no longer reverses.

    URL names are reversed here rather than by the client, which has no URLconf to reverse
    against. A stored name can stop resolving with nothing having been written to this table,
    because the host project owns its URLconf and may rename a route at any time. Letting that
    propagate would take down the whole spec over one step, so the step keeps its place in the
    tour and loses only its navigation: the renderer shows it on whatever page is current.
    """
    try:
        return step.get_path()
    except NoReverseMatch:
        logger.warning(
            "tourguide: step %s of tour '%s' names URL '%s', which no longer reverses",
            step.order,
            tour_slug,
            step.url_name,
        )
        return None


def _is_step_order(value):
    """Whether ``value`` is usable as a step position.

    ``isinstance(True, int)`` is true in Python, so booleans are excluded explicitly: a caller
    sending ``{"step": true}`` has filled in the wrong field, and would otherwise silently
    record step 1.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
