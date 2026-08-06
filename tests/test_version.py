from django.test import SimpleTestCase

import tourguide


class VersionTests(SimpleTestCase):
    """The package exposes a version string."""

    def test_version_is_exposed(self):
        """`tourguide.__version__` exists and is a non-empty string."""
        self.assertTrue(tourguide.__version__)
        self.assertIsInstance(tourguide.__version__, str)
