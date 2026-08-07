import sys
import unittest
from pathlib import Path

from django.test import SimpleTestCase

import tourguide

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


class VersionTests(SimpleTestCase):
    """The package exposes a version string."""

    def test_version_is_exposed(self):
        """`tourguide.__version__` exists and is a non-empty string."""
        self.assertTrue(tourguide.__version__)
        self.assertIsInstance(tourguide.__version__, str)

    @unittest.skipIf(sys.version_info < (3, 11), "tomllib arrived in 3.11")
    @unittest.skipUnless(PYPROJECT.exists(), "not a source checkout")
    def test_version_matches_the_packaging_metadata(self):
        """The two places the version is written agree.

        They are independent strings, so a release that bumps one and forgets the other
        publishes a distribution whose `__version__` reports something else. Nothing else
        catches that: both values are valid on their own.
        """
        import tomllib

        with PYPROJECT.open("rb") as f:
            declared = tomllib.load(f)["project"]["version"]

        self.assertEqual(tourguide.__version__, declared)
