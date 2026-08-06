"""Tests for the files the package ships.

The renderer is only useful if its assets actually reach a host project, and the ways that
breaks are quiet: a static file that never got packaged 404s in the browser, and a template
that moved raises only when something renders it.
"""

from pathlib import Path

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import TestCase

VENDOR = "tourguide/vendor"


class ShippedStaticFilesTests(TestCase):
    """Everything `{% tourguide %}` points at has to be findable by `collectstatic`."""

    def test_adapter_is_shipped(self):
        """The adapter is the package's own client code."""
        self.assertIsNotNone(finders.find("tourguide/tourguide.js"))

    def test_stylesheet_is_shipped(self):
        """The base stylesheet carries the documented class hooks."""
        self.assertIsNotNone(finders.find("tourguide/tourguide.css"))

    def test_driver_js_is_vendored(self):
        """driver.js is vendored rather than fetched, so there is no CDN to depend on.

        Nested a directory deeper than the adapter, which is exactly the arrangement a
        single-level `package-data` glob drops from the wheel without complaining.
        """
        found = finders.find(f"{VENDOR}/driver.js.iife.js")

        self.assertIsNotNone(found)
        self.assertIn("this.driver.js", Path(found).read_text())

    def test_driver_css_is_vendored(self):
        """driver.js needs its stylesheet, or a tour renders as unstyled boxes."""
        self.assertIsNotNone(finders.find(f"{VENDOR}/driver.css"))

    def test_driver_licence_travels_with_it(self):
        """Vendoring MIT code means shipping its licence alongside the code."""
        found = finders.find(f"{VENDOR}/LICENSE-driver.js")

        self.assertIsNotNone(found)
        self.assertIn("MIT", Path(found).read_text())


class ShippedTemplateTests(TestCase):
    """The templates the tags render, which are found by app directory rather than by path."""

    def test_loader_template_is_shipped(self):
        """`{% tourguide %}` renders this one."""
        self.assertIsNotNone(get_template("tourguide/loader.html"))

    def test_button_template_is_shipped(self):
        """`{% tourguide_button %}` renders this one."""
        self.assertIsNotNone(get_template("tourguide/button.html"))
