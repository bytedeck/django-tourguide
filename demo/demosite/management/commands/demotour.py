"""Seed the demo project with a tour that spans both pages, and a user to run it as.

The tour is the point of the demo: it crosses from Home to Settings partway through, which is
what actually exercises navigation and resume. Everything before the crossing is scenery.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from tourguide.models import Step, Tour

TOUR = {
    "slug": "getting-started",
    "name": "Getting started",
    "description": "A short tour that crosses from one page to another.",
    "icon": "compass",
}

# `url_name` rather than a literal path, since that is what a real project would write and it
# is the case worth demonstrating: the server reverses it, so the client never has to.
STEPS = [
    {
        "order": 0,
        "title": "Welcome",
        "content": "<p>This tour runs across two pages. Use <b>Next</b> to move through it.</p>",
        "url_name": "home",
    },
    {
        "order": 1,
        "element": "[data-tour='home-intro']",
        "title": "Where you are",
        "content": "<p>The tour anchors to elements by CSS selector, so it points at real controls.</p>",
        "side": "bottom",
    },
    {
        "order": 2,
        "element": "[data-tour='home-widget']",
        "title": "Something to point at",
        "content": "<p>Steps with no page of their own stay on whatever page the tour is already on.</p>",
        "side": "bottom",
    },
    {
        "order": 3,
        "element": "[data-tour='settings-intro']",
        "title": "A different page",
        "content": (
            "<p>This step lives on the Settings page, so choosing <b>Next</b> on the previous step "
            "saved your position and brought you here. Reload now and the tour picks up where it "
            "left off, because the position is on the server rather than in this tab.</p>"
        ),
        "url_name": "settings",
        "side": "bottom",
    },
    {
        "order": 4,
        "element": "[data-tour='settings-toggle']",
        "title": "Finding it again",
        "content": "<p>A host project would put its own control here. Finishing marks the tour complete.</p>",
        "side": "bottom",
    },
]


class Command(BaseCommand):
    """Create (or refresh) the demo tour and a user to view it as."""

    help = "Seed the demo tour and a demo user."

    def handle(self, *args, **options):
        """Replace any existing demo tour, then make sure the demo user exists."""
        tour, created = Tour.objects.update_or_create(slug=TOUR["slug"], defaults=TOUR)

        # Steps are replaced wholesale rather than matched up: this is seed data, and the
        # unique constraint on (tour, order) makes a partial update fiddly for no benefit.
        tour.steps.all().delete()
        for step in STEPS:
            Step.objects.create(tour=tour, **step)

        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} tour '{tour.slug}' with {len(STEPS)} steps."))

        user_model = get_user_model()
        user, user_created = user_model.objects.get_or_create(
            username="demo",
            defaults={"is_staff": True, "is_superuser": True},
        )
        if user_created:
            user.set_password("demo")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created user 'demo' with password 'demo'."))
        else:
            self.stdout.write("User 'demo' already exists.")

        self.stdout.write("Sign in at /admin/login/, then open / to see the tour start.")
