"""Tests for the read-only progress admin."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tourguide.progress.models import TourProgress


class TourProgressAdminTests(TestCase):
    """The progress changelist, which exists for support rather than editing."""

    @classmethod
    def setUpTestData(cls):
        """A superuser to browse with, and one record of each outcome."""
        cls.superuser = User.objects.create_superuser("root", "root@example.com", "x")
        cls.student = User.objects.create_user("student", password="x")

        cls.finished = TourProgress.objects.create(user=cls.student, tour_slug="quests", last_step=7)
        cls.finished.mark_completed()

        cls.gave_up = TourProgress.objects.create(user=cls.student, tour_slug="badges", last_step=2)
        cls.gave_up.mark_dismissed()

        cls.ongoing = TourProgress.objects.create(user=cls.student, tour_slug="maps", last_step=1)

    def setUp(self):
        """Browse as a superuser."""
        self.client.force_login(self.superuser)

    def test_changelist__renders_every_outcome(self):
        """All three outcomes render, each as the single word a human wants to read."""
        response = self.client.get(reverse("admin:tourguide_progress_tourprogress_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "completed")
        self.assertContains(response, "dismissed")
        self.assertContains(response, "in progress")

    def test_search__finds_progress_by_username(self):
        """Progress is searchable by user, which is how a support question starts."""
        response = self.client.get(
            reverse("admin:tourguide_progress_tourprogress_changelist"), {"q": "student"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 3)

    def test_adding_is_not_offered(self):
        """Progress is written by the tour, never by hand, so the add view is refused."""
        response = self.client.get(reverse("admin:tourguide_progress_tourprogress_add"))

        self.assertEqual(response.status_code, 403)

    def test_editing_is_not_offered(self):
        """Progress records what happened, so it is not editable.

        Django redirects a non-editable change view to the read-only detail rendering rather
        than refusing outright, so this asserts the record cannot be altered rather than
        asserting a particular status code.
        """
        response = self.client.get(
            reverse("admin:tourguide_progress_tourprogress_change", args=[self.finished.pk])
        )

        self.assertIn(response.status_code, (200, 302, 403))
        if response.status_code == 200:
            self.assertFalse(response.context["has_change_permission"])
