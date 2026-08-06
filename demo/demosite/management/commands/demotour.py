"""Set the demo project up: import its tour, and create a user to view it as.

The tour itself lives in ``demosite/fixtures/tours/getting-started.json`` and is imported by
``loadtours``, which is how a real project ships tour content. This command is the two lines
around that which are specific to running a demo.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Import the demo tour and make sure there is somebody to view it as."""

    help = "Set up the demo: import the tour and create the demo user."

    def add_arguments(self, parser):
        """Pass `--force` through, since re-running after editing the tour is the usual case."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-import the tour even if it has been edited in the admin.",
        )

    def handle(self, *args, **options):
        """Import the tour by fixture name, then create the demo user if it is missing."""
        # By name rather than by path: the fixture ships inside this app, which is the
        # arrangement a real project would use.
        call_command("loadtours", "getting-started", force=options["force"], stdout=self.stdout)

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username="demo",
            defaults={"is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("demo")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created user 'demo' with password 'demo'."))
        else:
            self.stdout.write("User 'demo' already exists.")

        self.stdout.write("Sign in at /admin/login/, then open / to see the tour start.")
