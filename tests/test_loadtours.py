"""Tests for the loadtours command.

Written against the command rather than its helpers, because what matters is what ends up in
the database after a run, and the interesting cases are all about the second run rather than
the first.
"""

import json
import tempfile
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from tourguide.models import Step, Tour
from tourguide.progress.models import TourProgress

FIXTURE = {
    "tours": [
        {
            "slug": "quests",
            "name": "Quests",
            "description": "How quests work",
            "icon": "compass",
            "audience": "staff",
            "order": 1,
            "steps": [
                {"order": 0, "title": "First", "content": "<p>One</p>", "element": "#one"},
                {"order": 1, "title": "Second", "content": "<p>Two</p>", "element": "#two"},
            ],
        }
    ]
}


def write_fixture(data):
    """Write a fixture to a temporary file and return its path."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(data, handle)
    handle.close()
    return handle.name


def load(*paths, **options):
    """Run the command, returning what it printed."""
    out = StringIO()
    call_command("loadtours", *paths, stdout=out, **options)
    return out.getvalue()


class LoadToursImportTests(TestCase):
    """The first run, which is the straightforward one."""

    def setUp(self):
        """A fixture on disk to import."""
        self.path = write_fixture(FIXTURE)

    def test_loadtours__creates_the_tour_and_its_steps(self):
        """A tour that does not exist yet is created whole."""
        load(self.path)

        tour = Tour.objects.get(slug="quests")
        self.assertEqual(tour.name, "Quests")
        self.assertEqual(tour.audience, Tour.Audience.STAFF)
        self.assertEqual([step.title for step in tour.steps.all()], ["First", "Second"])

    def test_loadtours__records_a_fingerprint(self):
        """The tour is stamped so a later run can tell whether anyone has edited it."""
        load(self.path)

        tour = Tour.objects.get(slug="quests")
        self.assertTrue(tour.import_checksum)
        self.assertFalse(tour.is_locally_edited())

    def test_loadtours__fields_left_out_take_their_defaults(self):
        """A fixture only has to say what it cares about."""
        load(write_fixture({"tours": [{"slug": "minimal", "name": "Minimal"}]}))

        tour = Tour.objects.get(slug="minimal")
        self.assertEqual(tour.audience, Tour.Audience.EVERYONE)
        self.assertTrue(tour.is_active)

    def test_loadtours__accepts_a_bare_list_of_tours(self):
        """The 'tours' key is a convenience, not a requirement."""
        load(write_fixture([{"slug": "bare", "name": "Bare"}]))

        self.assertTrue(Tour.objects.filter(slug="bare").exists())

    def test_loadtours__reads_several_fixtures(self):
        """Content can be split across files, which is how it ships per feature."""
        load(self.path, write_fixture({"tours": [{"slug": "badges", "name": "Badges"}]}))

        self.assertEqual(Tour.objects.count(), 2)


class LoadToursIdempotenceTests(TestCase):
    """Running twice, which is the case the command exists to get right."""

    def setUp(self):
        """An already-imported tour."""
        self.path = write_fixture(FIXTURE)
        load(self.path)
        self.tour = Tour.objects.get(slug="quests")

    def test_loadtours__second_run_changes_nothing(self):
        """Re-running reports the tour as unchanged rather than rewriting it."""
        output = load(self.path)

        self.assertIn("ok       quests", output)
        self.assertIn("1 unchanged", output)

    def test_loadtours__second_run_keeps_primary_keys(self):
        """Steps are matched on order rather than replaced, so their keys survive.

        Churning keys would be invisible today and would matter the moment anything ever
        refers to a step.
        """
        before = list(self.tour.steps.values_list("pk", flat=True))

        load(self.path)

        self.assertEqual(list(self.tour.steps.values_list("pk", flat=True)), before)

    def test_loadtours__progress_survives_a_reimport(self):
        """Progress refers to a tour by slug, so importing must not disturb it."""
        user = User.objects.create_user("student", password="x")
        TourProgress.objects.create(user=user, tour_slug="quests", last_step=1)

        load(self.path)

        progress = TourProgress.objects.get(user=user, tour_slug="quests")
        self.assertEqual(progress.last_step, 1)

    def test_loadtours__progress_survives_steps_changing(self):
        """Even when the step someone stopped on is gone, their record stays.

        The renderer starts such a tour over rather than guessing at a position that no
        longer means anything, but that is its decision to make and the record has to be
        there for it to make it.
        """
        user = User.objects.create_user("student", password="x")
        TourProgress.objects.create(user=user, tour_slug="quests", last_step=1)

        load(write_fixture({"tours": [{"slug": "quests", "name": "Quests", "steps": [{"order": 0, "title": "Only"}]}]}), force=True)

        self.assertEqual(TourProgress.objects.get(user=user, tour_slug="quests").last_step, 1)
        self.assertEqual(Tour.objects.get(slug="quests").steps.count(), 1)


class LoadToursChangeTests(TestCase):
    """What happens when the shipped content itself changes."""

    def setUp(self):
        """An already-imported tour."""
        self.path = write_fixture(FIXTURE)
        load(self.path)

    def test_loadtours__updates_changed_content(self):
        """A new release's wording reaches an untouched tour."""
        changed = json.loads(json.dumps(FIXTURE))
        changed["tours"][0]["name"] = "How quests work"

        load(write_fixture(changed))

        self.assertEqual(Tour.objects.get(slug="quests").name, "How quests work")

    def test_loadtours__adds_steps_added_to_the_fixture(self):
        """A step added upstream appears."""
        changed = json.loads(json.dumps(FIXTURE))
        changed["tours"][0]["steps"].append({"order": 2, "title": "Third"})

        load(write_fixture(changed))

        self.assertEqual([step.title for step in Tour.objects.get(slug="quests").steps.all()], ["First", "Second", "Third"])

    def test_loadtours__removes_steps_dropped_from_the_fixture(self):
        """A step removed upstream goes, rather than lingering forever."""
        changed = json.loads(json.dumps(FIXTURE))
        changed["tours"][0]["steps"] = changed["tours"][0]["steps"][:1]

        load(write_fixture(changed))

        self.assertEqual([step.title for step in Tour.objects.get(slug="quests").steps.all()], ["First"])

    def test_loadtours__refreshes_the_fingerprint_after_an_update(self):
        """An updated tour is not left looking edited."""
        changed = json.loads(json.dumps(FIXTURE))
        changed["tours"][0]["name"] = "How quests work"

        load(write_fixture(changed))

        self.assertFalse(Tour.objects.get(slug="quests").is_locally_edited())


class LoadToursLocalEditTests(TestCase):
    """The rule that a deck's own edits are not thrown away."""

    def setUp(self):
        """An imported tour that someone has since edited in the admin."""
        self.path = write_fixture(FIXTURE)
        load(self.path)
        Tour.objects.filter(slug="quests").update(name="Our own name for it")

    def test_loadtours__notices_the_edit(self):
        """The fingerprint is what makes the edit visible."""
        self.assertTrue(Tour.objects.get(slug="quests").is_locally_edited())

    def test_loadtours__leaves_an_edited_tour_alone(self):
        """Importing over somebody's work would destroy it, so by default it does not."""
        output = load(self.path)

        self.assertIn("skip     quests", output)
        self.assertEqual(Tour.objects.get(slug="quests").name, "Our own name for it")

    def test_loadtours__says_why_it_skipped(self):
        """The message names the cause and the switch, so it is actionable."""
        output = load(self.path)

        self.assertIn("edited since import", output)
        self.assertIn("--force", output)

    def test_loadtours__force_replaces_an_edited_tour(self):
        """Asking explicitly is how a deck gets back to the shipped content."""
        load(self.path, force=True)

        self.assertEqual(Tour.objects.get(slug="quests").name, "Quests")

    def test_loadtours__leaves_a_hand_written_tour_alone(self):
        """A tour nobody imported is somebody's own work, so it is not overwritten either."""
        Tour.objects.create(slug="homemade", name="Homemade")

        output = load(write_fixture({"tours": [{"slug": "homemade", "name": "Shipped"}]}))

        self.assertIn("not imported, written by hand", output)
        self.assertEqual(Tour.objects.get(slug="homemade").name, "Homemade")

    def test_loadtours__force_adopts_a_hand_written_tour(self):
        """With --force it becomes managed content, fingerprint and all."""
        Tour.objects.create(slug="homemade", name="Homemade")

        load(write_fixture({"tours": [{"slug": "homemade", "name": "Shipped"}]}), force=True)

        tour = Tour.objects.get(slug="homemade")
        self.assertEqual(tour.name, "Shipped")
        self.assertFalse(tour.is_locally_edited())

    def test_loadtours__edited_steps_count_as_an_edit(self):
        """The fingerprint covers steps too, not just the tour's own fields."""
        load(self.path, force=True)
        Step.objects.filter(tour__slug="quests", order=0).update(title="Reworded locally")

        output = load(self.path)

        self.assertIn("skip     quests", output)
        self.assertEqual(Step.objects.get(tour__slug="quests", order=0).title, "Reworded locally")


class LoadToursDryRunTests(TestCase):
    """Reporting without writing."""

    def setUp(self):
        """A fixture on disk."""
        self.path = write_fixture(FIXTURE)

    def test_dry_run__reports_what_it_would_create(self):
        """The report is the point, so it has to say what would happen."""
        output = load(self.path, dry_run=True)

        self.assertIn("create   quests", output)

    def test_dry_run__writes_nothing(self):
        """Nothing reaches the database, which is the other half of the point."""
        load(self.path, dry_run=True)

        self.assertEqual(Tour.objects.count(), 0)

    def test_dry_run__says_it_wrote_nothing(self):
        """Saying so avoids the report being mistaken for a run."""
        self.assertIn("nothing was written", load(self.path, dry_run=True).lower())

    def test_dry_run__does_not_change_an_existing_tour(self):
        """A dry run over an existing tour rolls back rather than half-applying."""
        load(self.path)
        changed = json.loads(json.dumps(FIXTURE))
        changed["tours"][0]["name"] = "Rewritten"

        load(write_fixture(changed), dry_run=True)

        self.assertEqual(Tour.objects.get(slug="quests").name, "Quests")


class LoadToursFixtureResolutionTests(TestCase):
    """Finding fixtures, by path and by name."""

    def test_loadtours__finds_a_fixture_inside_an_installed_app(self):
        """Content ships inside the app it belongs to, the way `loaddata` works."""
        output = load("demo-tour")

        self.assertIn("create   packaged-demo", output)
        self.assertTrue(Tour.objects.filter(slug="packaged-demo").exists())

    def test_loadtours__accepts_the_name_with_its_extension(self):
        """Both spellings work, since either is a reasonable thing to type."""
        load("demo-tour.json")

        self.assertTrue(Tour.objects.filter(slug="packaged-demo").exists())

    def test_loadtours__reports_a_fixture_it_cannot_find(self):
        """The error says where it looked, rather than just failing."""
        with self.assertRaises(CommandError) as caught:
            load("no-such-fixture")

        self.assertIn("fixtures/tours/", str(caught.exception))


class LoadToursBadInputTests(TestCase):
    """Fixtures that are wrong, which should fail clearly rather than halfway."""

    def test_loadtours__rejects_invalid_json(self):
        """A malformed file names itself in the error."""
        path = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        path.write("{not json")
        path.close()

        with self.assertRaises(CommandError) as caught:
            load(path.name)

        self.assertIn("not valid JSON", str(caught.exception))

    def test_loadtours__rejects_a_fixture_that_is_not_a_list_of_tours(self):
        """A plausible-looking file with the wrong shape is caught before writing."""
        with self.assertRaises(CommandError) as caught:
            load(write_fixture({"tours": {"slug": "quests"}}))

        self.assertIn("list of tours", str(caught.exception))

    def test_loadtours__rejects_a_tour_with_no_slug(self):
        """The slug is the identity everything else keys on, so it cannot be missing."""
        with self.assertRaises(CommandError) as caught:
            load(write_fixture({"tours": [{"name": "Nameless"}]}))

        self.assertIn("needs a slug", str(caught.exception))

    def test_loadtours__reports_an_empty_fixture(self):
        """An empty file is not an error, but it should not look like a successful import."""
        self.assertIn("No tours found", load(write_fixture({"tours": []})))

    def test_loadtours__leaves_nothing_behind_when_a_later_tour_fails(self):
        """The run is one transaction, so a bad tour does not half-apply the good ones.

        A fixture that failed partway through would otherwise leave content in a state
        matching neither the release nor what was there before.
        """
        with self.assertRaises(CommandError):
            load(write_fixture({"tours": [{"slug": "fine", "name": "Fine"}, {"name": "Broken"}]}))

        self.assertFalse(Tour.objects.filter(slug="fine").exists())


class TourImportDataTests(TestCase):
    """The shape a tour reports itself in, which both the fingerprint and comparison use."""

    def test_as_import_data__round_trips_through_the_command(self):
        """A tour exported and re-imported is unchanged, which is what makes it a fixture."""
        load(write_fixture(FIXTURE))
        exported = Tour.objects.get(slug="quests").as_import_data()

        load(write_fixture({"tours": [exported]}))

        self.assertIn("ok       quests", load(write_fixture({"tours": [exported]})))

    def test_content_checksum__changes_when_a_step_changes(self):
        """The fingerprint has to notice step edits, or they would be silently overwritten."""
        load(write_fixture(FIXTURE))
        tour = Tour.objects.get(slug="quests")
        before = tour.content_checksum()

        tour.steps.filter(order=0).update(title="Different")

        self.assertNotEqual(Tour.objects.get(slug="quests").content_checksum(), before)
