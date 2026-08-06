"""Import tour content from JSON fixtures.

Tours live in the database so they can be edited, but they are also product content that
ships with a release. This command reconciles those two facts, and it is what makes keeping
one shared copy of the tours practical: updating content becomes a command run rather than a
data migration per tenant.

It is an upsert, not a load. Tours are matched by slug and steps by order, so re-running
changes nothing the second time, leaves primary keys alone, and never touches progress
records, which refer to a tour by slug rather than by key.
"""

import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tourguide.models import IMPORTED_STEP_FIELDS, IMPORTED_TOUR_FIELDS, Step, Tour


class Command(BaseCommand):
    """Import or refresh tours from one or more JSON fixtures."""

    help = "Import tour definitions from JSON fixtures, leaving locally edited tours alone."

    def add_arguments(self, parser):
        """Fixtures to read, plus the two switches that change what gets written."""
        parser.add_argument(
            "fixtures",
            nargs="+",
            help="Fixture paths, or names to look up in the fixtures/tours/ directory of an installed app.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite tours that have been edited since they were imported.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        """Read every fixture first, then apply them in one transaction."""
        tours = []
        for name in options["fixtures"]:
            tours.extend(self._read(name))

        if not tours:
            self.stdout.write("No tours found in the given fixtures.")
            return

        # One transaction for the lot: a fixture that fails halfway through would otherwise
        # leave content half-updated, which is worse than not having run at all.
        with transaction.atomic():
            counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
            for data in tours:
                counts[self._apply(data, force=options["force"], dry_run=options["dry_run"])] += 1

            if options["dry_run"]:
                transaction.set_rollback(True)

        self._report(counts, dry_run=options["dry_run"])

    # ------------------------------------------------------------------ reading ----

    def _read(self, name):
        """Return the tours in one fixture, whether named by path or by fixture name."""
        path = self._resolve(name)
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            raise CommandError(f"{path} is not valid JSON: {error}") from error

        tours = data.get("tours") if isinstance(data, dict) else data
        if not isinstance(tours, list):
            raise CommandError(f"{path} should contain a list of tours, or an object with a 'tours' key.")
        return tours

    def _resolve(self, name):
        """Find a fixture by path, or by name inside an installed app's fixtures/tours/.

        Mirrors how `loaddata` lets content ship inside the app it belongs to, which is the
        point of the command: a release carries its tours rather than a deployment step
        having to know where they live.
        """
        direct = Path(name)
        if direct.is_file():
            return direct

        candidates = [name, f"{name}.json"]
        for config in apps.get_app_configs():
            for candidate in candidates:
                found = Path(config.path) / "fixtures" / "tours" / candidate
                if found.is_file():
                    return found

        raise CommandError(f"Could not find fixture '{name}' as a path or in any installed app's fixtures/tours/ directory.")

    # ------------------------------------------------------------------ writing ----

    def _apply(self, data, force, dry_run):
        """Create, update, or leave alone the tour described by ``data``."""
        slug = data.get("slug")
        if not slug:
            raise CommandError(f"Every tour needs a slug: {data!r}")

        existing = Tour.objects.filter(slug=slug).first()
        if existing is None:
            if not dry_run:
                self._write(Tour(slug=slug), data)
            self.stdout.write(self.style.SUCCESS(f"  create   {slug}"))
            return "created"

        if existing.as_import_data() == self._normalised(data):
            self.stdout.write(f"  ok       {slug}")
            return "unchanged"

        if existing.is_locally_edited() and not force:
            reason = "edited since import" if existing.import_checksum else "not imported, written by hand"
            self.stdout.write(self.style.WARNING(f"  skip     {slug} ({reason}, use --force to replace)"))
            return "skipped"

        if not dry_run:
            self._write(existing, data)
        self.stdout.write(self.style.SUCCESS(f"  update   {slug}"))
        return "updated"

    def _write(self, tour, data):
        """Write the tour and reconcile its steps, then record the new fingerprint."""
        for field in IMPORTED_TOUR_FIELDS:
            if field in data:
                setattr(tour, field, data[field])
        tour.save()

        incoming = {step["order"]: step for step in data.get("steps", [])}

        # Steps are matched on order rather than replaced wholesale, so a step that did not
        # change keeps its primary key. Deleting and recreating would churn keys for no
        # reason, and would matter the moment anything ever points at a step.
        tour.steps.exclude(order__in=incoming).delete()
        for order, step_data in incoming.items():
            step = tour.steps.filter(order=order).first() or Step(tour=tour, order=order)
            for field in IMPORTED_STEP_FIELDS:
                if field in step_data:
                    setattr(step, field, step_data[field])
            step.save()

        # Computed after writing, from the database rather than from the fixture, so the
        # fingerprint describes what is actually stored. A fixture that omits a field leaves
        # the model default in place, and the fingerprint has to reflect that or the next run
        # would read it as a local edit.
        tour.refresh_from_db()
        Tour.objects.filter(pk=tour.pk).update(import_checksum=tour.content_checksum())

    def _normalised(self, data):
        """The fixture as a stored tour would look, so the two can be compared directly.

        A fixture leaves out anything it is happy to take the default for, so comparing it
        raw against a stored tour would report a difference on every optional field.
        """
        defaults = Tour(slug=data["slug"])
        normalised = {
            "slug": data["slug"],
            **{field: data.get(field, getattr(defaults, field)) for field in IMPORTED_TOUR_FIELDS},
            "steps": [],
        }
        for step_data in data.get("steps", []):
            step_defaults = Step()
            normalised["steps"].append({field: step_data.get(field, getattr(step_defaults, field)) for field in IMPORTED_STEP_FIELDS})
        normalised["steps"].sort(key=lambda step: step["order"])
        return normalised

    # ---------------------------------------------------------------- reporting ----

    def _report(self, counts, dry_run):
        """Summarise the run, and say plainly when nothing was written."""
        summary = ", ".join(f"{count} {name}" for name, count in counts.items() if count)
        self.stdout.write(summary or "nothing to do")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing was written."))
