from django.apps import apps
from django.test import SimpleTestCase

from tourguide.apps import TourguideConfig
from tourguide.progress.apps import TourguideProgressConfig


class AppConfigTests(SimpleTestCase):
    """The two apps load independently and keep distinct, non-generic app labels."""

    def test_both_apps_are_installed(self):
        """Both apps register with Django, which is what lets a host project split them."""
        self.assertTrue(apps.is_installed("tourguide"))
        self.assertTrue(apps.is_installed("tourguide.progress"))

    def test_definitions_app_label(self):
        """The definitions app keeps the plain `tourguide` label."""
        self.assertEqual(TourguideConfig.name, "tourguide")
        self.assertEqual(apps.get_app_config("tourguide").label, "tourguide")

    def test_progress_app_label__not_generic(self):
        """The progress app overrides its label.

        Django would otherwise derive `progress` from the last component of the dotted app
        name, which is generic enough to collide in a host project.
        """
        self.assertEqual(TourguideProgressConfig.name, "tourguide.progress")
        self.assertEqual(apps.get_app_config("tourguide_progress").label, "tourguide_progress")

    def test_app_labels_are_distinct(self):
        """The two labels differ, so their models and tables never collide."""
        self.assertNotEqual(
            apps.get_app_config("tourguide").label,
            apps.get_app_config("tourguide_progress").label,
        )
