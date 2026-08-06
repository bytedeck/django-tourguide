"""Tests for the tour definition models."""

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch

from tourguide.models import Step, Tour


class TourStrTests(SimpleTestCase):
    """`Tour.__str__` is the name, which is what the admin and the picker show."""

    def test_str__is_the_name(self):
        """A tour renders as its human-readable name, not its slug."""
        self.assertEqual(str(Tour(name="Quests", slug="quests")), "Quests")


class TourOrderingTests(TestCase):
    """Tours sort by explicit order, then name."""

    def test_ordering__by_order_then_name(self):
        """Explicit order wins, and ties fall back to alphabetical rather than insertion order."""
        Tour.objects.create(slug="c", name="Cherry", order=1)
        Tour.objects.create(slug="a", name="Apple", order=2)
        Tour.objects.create(slug="b", name="Banana", order=1)

        self.assertEqual([t.name for t in Tour.objects.all()], ["Banana", "Cherry", "Apple"])


class TourVisibilityTests(TestCase):
    """`is_visible_to` is the audience gate, and is what the endpoints enforce."""

    @classmethod
    def setUpTestData(cls):
        """Create one user of each kind."""
        cls.student = User.objects.create_user("student", password="x")
        cls.staff = User.objects.create_user("staff", password="x", is_staff=True)
        cls.superuser = User.objects.create_superuser("root", password="x")

    def test_everyone_tour__visible_to_all_authenticated_users(self):
        """An `everyone` tour is offered to any signed-in user, whatever their flags."""
        tour = Tour.objects.create(slug="t", name="T", audience=Tour.Audience.EVERYONE)

        self.assertTrue(tour.is_visible_to(self.student))
        self.assertTrue(tour.is_visible_to(self.staff))
        self.assertTrue(tour.is_visible_to(self.superuser))

    def test_staff_tour__hidden_from_regular_users(self):
        """A staff-only tour is not offered to a regular user."""
        tour = Tour.objects.create(slug="t", name="T", audience=Tour.Audience.STAFF)

        self.assertFalse(tour.is_visible_to(self.student))
        self.assertTrue(tour.is_visible_to(self.staff))

    def test_staff_tour__visible_to_superuser_without_staff_flag(self):
        """A superuser sees a staff-only tour even without `is_staff`.

        Not every project sets both flags, and a superuser being shown less than a teacher
        would be surprising.
        """
        root = User.objects.create_superuser("root2", password="x")
        root.is_staff = False
        root.save()
        tour = Tour.objects.create(slug="t", name="T", audience=Tour.Audience.STAFF)

        self.assertTrue(tour.is_visible_to(root))

    def test_superuser_tour__hidden_from_staff(self):
        """A superuser-only tour is not offered to ordinary staff."""
        tour = Tour.objects.create(slug="t", name="T", audience=Tour.Audience.SUPERUSER)

        self.assertFalse(tour.is_visible_to(self.staff))
        self.assertTrue(tour.is_visible_to(self.superuser))

    def test_inactive_tour__hidden_from_everyone(self):
        """An inactive tour is withdrawn from everyone, including superusers."""
        tour = Tour.objects.create(slug="t", name="T", is_active=False)

        self.assertFalse(tour.is_visible_to(self.student))
        self.assertFalse(tour.is_visible_to(self.superuser))

    def test_anonymous_user__never_sees_a_tour(self):
        """Anonymous users get no tour, since there is nowhere to record their progress."""
        tour = Tour.objects.create(slug="t", name="T", audience=Tour.Audience.EVERYONE)

        self.assertFalse(tour.is_visible_to(AnonymousUser()))

    def test_no_user__never_sees_a_tour(self):
        """A missing user is treated as anonymous rather than raising."""
        tour = Tour.objects.create(slug="t", name="T", audience=Tour.Audience.EVERYONE)

        self.assertFalse(tour.is_visible_to(None))


class StepTests(TestCase):
    """Step ordering, string form, and the tour relationship."""

    @classmethod
    def setUpTestData(cls):
        """A tour to hang steps off."""
        cls.tour = Tour.objects.create(slug="t", name="Tour")

    def test_str__names_the_tour_and_position(self):
        """A step identifies itself by tour and position, which is what the admin lists."""
        step = Step.objects.create(tour=self.tour, order=2, title="Second")

        self.assertEqual(str(step), "Tour (2)")

    def test_steps_ordered_by_position(self):
        """Steps come back in tour order regardless of the order they were created."""
        Step.objects.create(tour=self.tour, order=2, title="Second")
        Step.objects.create(tour=self.tour, order=0, title="First")
        Step.objects.create(tour=self.tour, order=1, title="Middle")

        self.assertEqual([s.title for s in self.tour.steps.all()], ["First", "Middle", "Second"])

    def test_duplicate_order_within_a_tour__rejected(self):
        """Two steps cannot claim the same position in one tour, which would make order arbitrary."""
        Step.objects.create(tour=self.tour, order=0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Step.objects.create(tour=self.tour, order=0)

    def test_same_order_in_different_tours__allowed(self):
        """The uniqueness is per tour, so every tour can have its own step 0."""
        other = Tour.objects.create(slug="other", name="Other")
        Step.objects.create(tour=self.tour, order=0)

        Step.objects.create(tour=other, order=0)  # must not raise

        self.assertEqual(Step.objects.filter(order=0).count(), 2)

    def test_deleting_a_tour_deletes_its_steps(self):
        """Steps have no meaning without their tour, so they go with it."""
        Step.objects.create(tour=self.tour, order=0)
        self.tour.delete()

        self.assertEqual(Step.objects.count(), 0)


class StepPageTests(TestCase):
    """Which page a step belongs to, and the validation that keeps that resolvable.

    `admin:index` stands in as a URL name that genuinely reverses. What matters is that
    reversing happens at all, not which page it lands on.
    """

    @classmethod
    def setUpTestData(cls):
        """A tour to hang steps off."""
        cls.tour = Tour.objects.create(slug="t", name="Tour")

    def test_get_path__from_url_name(self):
        """A step naming a URL resolves it to a path."""
        step = Step(tour=self.tour, order=0, url_name="admin:index")

        self.assertEqual(step.get_path(), "/admin/")

    def test_get_path__from_literal_path(self):
        """A step with a literal path returns it unchanged."""
        step = Step(tour=self.tour, order=0, path="/settings/")

        self.assertEqual(step.get_path(), "/settings/")

    def test_get_path__none_when_not_page_specific(self):
        """A step naming neither belongs to whatever page the tour is already on."""
        step = Step(tour=self.tour, order=0)

        self.assertIsNone(step.get_path())

    def test_clean__rejects_both_url_name_and_path(self):
        """Setting both is ambiguous, so it is caught at authoring time."""
        step = Step(tour=self.tour, order=0, url_name="admin:index", path="/settings/")

        with self.assertRaises(ValidationError) as ctx:
            step.clean()

        self.assertIn("path", ctx.exception.message_dict)

    def test_clean__rejects_url_name_that_does_not_reverse(self):
        """A typo in a URL name is caught here rather than as a broken tour in the browser."""
        step = Step(tour=self.tour, order=0, url_name="no:such:url")

        with self.assertRaises(ValidationError) as ctx:
            step.clean()

        self.assertIn("url_name", ctx.exception.message_dict)

    def test_clean__rejects_url_name_with_wrong_arguments(self):
        """A URL name that needs different arguments than given does not reverse either."""
        step = Step(tour=self.tour, order=0, url_name="admin:index", url_args=["unexpected"])

        with self.assertRaises(ValidationError) as ctx:
            step.clean()

        self.assertIn("url_name", ctx.exception.message_dict)

    def test_clean__rejects_absolute_url(self):
        """A host in the path would pin the tour to one domain, breaking per-tenant subdomains."""
        step = Step(tour=self.tour, order=0, path="https://example.com/settings/")

        with self.assertRaises(ValidationError) as ctx:
            step.clean()

        self.assertIn("path", ctx.exception.message_dict)

    def test_clean__rejects_protocol_relative_url(self):
        """A protocol-relative URL is still a host reference, so it is rejected too."""
        step = Step(tour=self.tour, order=0, path="//example.com/settings/")

        with self.assertRaises(ValidationError) as ctx:
            step.clean()

        self.assertIn("path", ctx.exception.message_dict)

    def test_clean__rejects_relative_path_without_leading_slash(self):
        """A path is resolved against the site root, so it has to start there."""
        step = Step(tour=self.tour, order=0, path="settings/")

        with self.assertRaises(ValidationError) as ctx:
            step.clean()

        self.assertIn("path", ctx.exception.message_dict)

    def test_clean__accepts_a_valid_url_name(self):
        """The ordinary case passes validation."""
        step = Step(tour=self.tour, order=0, url_name="admin:index")

        step.clean()  # must not raise

    def test_clean__accepts_a_step_with_no_page(self):
        """A step that stays on the current page is valid and common."""
        step = Step(tour=self.tour, order=0, element="#thing")

        step.clean()  # must not raise

    def test_both_url_name_and_path__rejected_by_the_database(self):
        """The database refuses a step naming both, not just `clean()`.

        Steps also arrive from fixtures, data migrations and bulk writes, none of which
        validate, and a row with both set would silently ignore its path.
        """
        with self.assertRaises(IntegrityError), transaction.atomic():
            Step.objects.create(tour=self.tour, order=0, url_name="admin:index", path="/settings/")

    def test_url_name_alone__accepted_by_the_database(self):
        """The constraint permits a URL name on its own."""
        Step.objects.create(tour=self.tour, order=0, url_name="admin:index")  # must not raise

    def test_path_alone__accepted_by_the_database(self):
        """The constraint permits a path on its own."""
        Step.objects.create(tour=self.tour, order=0, path="/settings/")  # must not raise

    def test_neither__accepted_by_the_database(self):
        """The constraint permits a step with no page of its own, which is the common case."""
        Step.objects.create(tour=self.tour, order=0)  # must not raise

    def test_get_path__raises_when_a_stored_url_name_stops_resolving(self):
        """`get_path()` does not hide a broken URL name.

        A host project can rename a route at any time, which invalidates stored steps with no
        write to this table. Callers that render to a user are expected to handle this; the
        admin does.
        """
        Step.objects.create(tour=self.tour, order=0, url_name="admin:index")
        # `update()` bypasses validation, which is how a stale name gets stored in practice.
        Step.objects.filter(order=0).update(url_name="gone:away")

        with self.assertRaises(NoReverseMatch):
            Step.objects.get(order=0).get_path()
