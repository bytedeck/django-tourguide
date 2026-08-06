"""Tests for per-user tour progress."""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from tourguide.models import Tour
from tourguide.progress.models import TourProgress


class TourProgressBasicsTests(TestCase):
    """Identity, ordering, and the relationship to the user."""

    @classmethod
    def setUpTestData(cls):
        """A user and a tour to track progress against."""
        cls.user = User.objects.create_user("student", password="x")
        cls.tour = Tour.objects.create(slug="quests", name="Quests")

    def test_str__names_the_user_and_tour(self):
        """Progress identifies itself by whose it is and which tour, which is what the admin lists."""
        progress = TourProgress.objects.create(user=self.user, tour_slug="quests")

        self.assertEqual(str(progress), "student / quests")

    def test_one_record_per_user_and_tour(self):
        """A user cannot accumulate two progress records for the same tour."""
        TourProgress.objects.create(user=self.user, tour_slug="quests")

        with self.assertRaises(IntegrityError), transaction.atomic():
            TourProgress.objects.create(user=self.user, tour_slug="quests")

    def test_a_user_can_have_progress_on_several_tours(self):
        """Progress is per tour, so several tours can be in flight at once.

        The tour system this replaces got exactly this wrong: its `CompletedTour.user` was a
        `OneToOneField`, which allowed only one completed tour per user ever.
        """
        TourProgress.objects.create(user=self.user, tour_slug="quests")
        TourProgress.objects.create(user=self.user, tour_slug="badges")

        self.assertEqual(self.user.tour_progress.count(), 2)

    def test_several_users_can_have_progress_on_one_tour(self):
        """The uniqueness is per user, so one tour can be in flight for many people."""
        other = User.objects.create_user("teacher", password="x")
        TourProgress.objects.create(user=self.user, tour_slug="quests")

        TourProgress.objects.create(user=other, tour_slug="quests")  # must not raise

        self.assertEqual(TourProgress.objects.filter(tour_slug="quests").count(), 2)

    def test_deleting_a_user_deletes_their_progress(self):
        """Progress has no meaning without its user, so it goes with them."""
        TourProgress.objects.create(user=self.user, tour_slug="quests")
        self.user.delete()

        self.assertEqual(TourProgress.objects.count(), 0)

    def test_starts_at_step_zero_and_unfinished(self):
        """A fresh record represents someone who has been offered the tour but not moved."""
        progress = TourProgress.objects.create(user=self.user, tour_slug="quests")

        self.assertEqual(progress.last_step, 0)
        self.assertIsNone(progress.completed_at)
        self.assertIsNone(progress.dismissed_at)
        self.assertFalse(progress.is_finished)


class TourProgressTourResolutionTests(TestCase):
    """Resolving the slug back to a tour, including when it no longer resolves."""

    @classmethod
    def setUpTestData(cls):
        """A user, a tour, and progress pointing at it."""
        cls.user = User.objects.create_user("student", password="x")
        cls.tour = Tour.objects.create(slug="quests", name="Quests")
        cls.progress = TourProgress.objects.create(user=cls.user, tour_slug="quests")

    def test_tour__resolves_the_slug(self):
        """The slug resolves to the tour it names."""
        self.assertEqual(self.progress.tour, self.tour)

    def test_tour__is_none_when_the_tour_is_gone(self):
        """Progress outlives the tour it names, and says so rather than raising.

        There is no foreign key, so deleting a tour leaves progress behind. Returning `None`
        is the documented contract: callers treat it as nothing to show.
        """
        self.tour.delete()

        self.assertIsNone(TourProgress.objects.get(pk=self.progress.pk).tour)

    def test_tour__is_none_when_the_slug_never_matched(self):
        """A slug that never named a real tour resolves to nothing rather than erroring."""
        orphan = TourProgress.objects.create(user=self.user, tour_slug="never-existed")

        self.assertIsNone(orphan.tour)

    def test_tour__is_not_cached_across_content_changes(self):
        """Re-reading picks up a re-imported tour rather than serving a stale one.

        `loadtours` replaces shipped content in place, so a cached resolution on a long-lived
        instance would keep returning the old object.
        """
        self.assertEqual(self.progress.tour.name, "Quests")
        Tour.objects.filter(slug="quests").update(name="How quests work")

        self.assertEqual(self.progress.tour.name, "How quests work")


class TourProgressRecordStepTests(TestCase):
    """Recording how far the user got."""

    @classmethod
    def setUpTestData(cls):
        """A user to track."""
        cls.user = User.objects.create_user("student", password="x")

    def setUp(self):
        """Fresh progress for each test."""
        self.progress = TourProgress.objects.create(user=self.user, tour_slug="quests")

    def test_record_step__advances(self):
        """Reaching a later step moves the stored position forward."""
        self.progress.record_step(3)

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.last_step, 3)

    def test_record_step__does_not_rewind(self):
        """Stepping back through a tour does not lose the furthest point reached.

        Going backwards is normal use of a Previous button. If it rewound the stored position,
        resuming later would drop the user earlier than they actually got.
        """
        self.progress.record_step(5)

        self.progress.record_step(2)

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.last_step, 5)

    def test_record_step__same_step_is_a_no_op(self):
        """Re-reporting the current step changes nothing."""
        self.progress.record_step(4)

        self.progress.record_step(4)

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.last_step, 4)

    def test_record_step__a_stale_instance_cannot_rewind_the_row(self):
        """A second instance loaded earlier cannot undo progress made by the first.

        Two tabs open on the same tour are enough to have two instances in play. Comparing
        against this instance's copy rather than the stored row would let whichever request
        loaded earlier write the lower value last.
        """
        ahead = TourProgress.objects.get(pk=self.progress.pk)
        behind = TourProgress.objects.get(pk=self.progress.pk)

        ahead.record_step(5)
        behind.record_step(3)

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.last_step, 5)

    def test_record_step__a_stale_instance_catches_up_after_a_refused_write(self):
        """The instance whose write was refused still ends up holding the true value."""
        ahead = TourProgress.objects.get(pk=self.progress.pk)
        behind = TourProgress.objects.get(pk=self.progress.pk)
        ahead.record_step(5)

        behind.record_step(3)

        self.assertEqual(behind.last_step, 5)


class TourProgressOutcomeTests(TestCase):
    """Completion and dismissal, which are deliberately distinct."""

    @classmethod
    def setUpTestData(cls):
        """A user to track."""
        cls.user = User.objects.create_user("student", password="x")

    def setUp(self):
        """Fresh progress for each test."""
        self.progress = TourProgress.objects.create(user=self.user, tour_slug="quests")

    def test_mark_completed__records_the_time(self):
        """Finishing stamps a completion time and counts as finished."""
        self.progress.mark_completed()

        self.progress.refresh_from_db()
        self.assertIsNotNone(self.progress.completed_at)
        self.assertIsNone(self.progress.dismissed_at)
        self.assertTrue(self.progress.is_finished)

    def test_mark_dismissed__records_the_time(self):
        """Giving up stamps a dismissal time and also counts as finished.

        Both outcomes stop the tour reappearing, which is why `is_finished` covers each.
        """
        self.progress.mark_dismissed()

        self.progress.refresh_from_db()
        self.assertIsNotNone(self.progress.dismissed_at)
        self.assertIsNone(self.progress.completed_at)
        self.assertTrue(self.progress.is_finished)

    def test_completion_and_dismissal_are_distinguishable(self):
        """The two outcomes are stored separately, so reporting can tell them apart.

        Collapsing them into one flag would lose the difference between a tour that works and
        one everybody abandons.
        """
        finished = self.progress
        finished.mark_completed()
        gave_up = TourProgress.objects.create(user=self.user, tour_slug="badges")
        gave_up.mark_dismissed()

        self.assertEqual(TourProgress.objects.filter(completed_at__isnull=False).count(), 1)
        self.assertEqual(TourProgress.objects.filter(dismissed_at__isnull=False).count(), 1)

    def test_mark_completed__keeps_the_original_time(self):
        """Repeating a tour does not rewrite when it was first finished."""
        self.progress.mark_completed()
        first = self.progress.completed_at

        self.progress.mark_completed()

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.completed_at, first)

    def test_mark_dismissed__keeps_the_original_time(self):
        """Dismissing twice keeps the first dismissal time, for the same reason."""
        self.progress.mark_dismissed()
        first = self.progress.dismissed_at

        self.progress.mark_dismissed()

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.dismissed_at, first)

    def test_mark_completed__a_stale_instance_cannot_replace_the_timestamp(self):
        """A second instance that still believes the tour is unfinished cannot restamp it.

        Testing "already set?" against this instance's copy rather than the stored row would
        let a concurrent request overwrite the original completion time.
        """
        first = TourProgress.objects.get(pk=self.progress.pk)
        second = TourProgress.objects.get(pk=self.progress.pk)
        first.mark_completed()
        original = TourProgress.objects.get(pk=self.progress.pk).completed_at

        second.mark_completed()

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.completed_at, original)
        self.assertEqual(second.completed_at, original)

    def test_mark_dismissed__a_stale_instance_cannot_replace_the_timestamp(self):
        """Dismissal is guarded the same way, for the same reason."""
        first = TourProgress.objects.get(pk=self.progress.pk)
        second = TourProgress.objects.get(pk=self.progress.pk)
        first.mark_dismissed()
        original = TourProgress.objects.get(pk=self.progress.pk).dismissed_at

        second.mark_dismissed()

        self.progress.refresh_from_db()
        self.assertEqual(self.progress.dismissed_at, original)
        self.assertEqual(second.dismissed_at, original)

    def test_is_finished__false_while_in_progress(self):
        """Someone partway through has not finished, so the tour may still resume."""
        self.progress.record_step(2)

        self.assertFalse(self.progress.is_finished)

    def test_started_at__is_set_on_creation(self):
        """The record stamps when the tour was first offered."""
        self.assertIsNotNone(self.progress.started_at)
        self.assertLessEqual(self.progress.started_at, timezone.now())
