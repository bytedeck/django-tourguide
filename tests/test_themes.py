"""Tests for themes.

A theme is data that reaches the client in the config, so these check what gets resolved and
what gets emitted. What the browser then does with it is the adapter's job and is verified in
the demo rather than here.
"""

import json
import re

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings

from tourguide.checks import check_theme
from tourguide.themes import BOOTSTRAP3, BOOTSTRAP4, BOOTSTRAP5, THEMES, get_theme


def render(source, **context):
    """Render a template fragment with the tag library loaded."""
    return Template("{% load tourguide %}" + source).render(Context(context))


def embedded_config(html):
    """Pull the config back out of rendered markup, the way the client does."""
    body = re.search(r'<script id="tourguide-config" type="application/json">(.*?)</script>', html, re.DOTALL).group(1)
    text = body.replace("\\u003C", "<").replace("\\u003E", ">").replace("\\u0026", "&")
    return json.loads(text)


class ThemeResolutionTests(TestCase):
    """Turning a name into a class map."""

    def test_get_theme__is_none_by_default(self):
        """With nothing configured there is no theme, which is the plain driver.js look."""
        self.assertIsNone(get_theme())

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_get_theme__reads_the_setting(self):
        """The setting is the normal way to choose one, since a project has one design system."""
        self.assertEqual(get_theme(), BOOTSTRAP5)

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_get_theme__argument_overrides_the_setting(self):
        """A project part-way through changing frameworks has both in the tree at once."""
        self.assertEqual(get_theme("bootstrap3"), BOOTSTRAP3)

    def test_get_theme__rejects_an_unknown_name(self):
        """A typo raises rather than rendering unstyled, which looks like no theme at all."""
        with self.assertRaises(ImproperlyConfigured) as caught:
            get_theme("bootstrap6")

        self.assertIn("bootstrap5", str(caught.exception))

    def test_ships_all_three_bootstrap_versions(self):
        """The three are separate themes because the frameworks genuinely differ."""
        self.assertEqual(sorted(THEMES), ["bootstrap3", "bootstrap4", "bootstrap5"])


class BootstrapDifferenceTests(TestCase):
    """The specific places the three versions diverge, each of which forced a separate theme."""

    def test_bootstrap3__uses_btn_default_for_the_secondary_button(self):
        """`btn-default` exists only in Bootstrap 3; 4 renamed it."""
        self.assertIn("btn-default", BOOTSTRAP3["prevButton"])

    def test_bootstrap4__uses_btn_secondary_for_the_secondary_button(self):
        """Bootstrap 4 replaced `btn-default` with `btn-secondary`."""
        self.assertIn("btn-secondary", BOOTSTRAP4["prevButton"])
        self.assertNotIn("btn-default", BOOTSTRAP4["prevButton"])

    def test_bootstrap3_and_4__use_the_old_close_class(self):
        """`.close` is the Bootstrap 3 and 4 spelling."""
        self.assertEqual(BOOTSTRAP3["closeButton"], "close")
        self.assertEqual(BOOTSTRAP4["closeButton"], "close")

    def test_bootstrap5__uses_btn_close(self):
        """Bootstrap 5 renamed it and changed how it draws itself."""
        self.assertEqual(BOOTSTRAP5["closeButton"], "btn-close")

    def test_bootstrap5__clears_the_close_label(self):
        """`.btn-close` draws its own icon, so driver.js's glyph would show as a second one.

        Bootstrap 3 and 4 style a glyph the markup supplies, so theirs is left in place. This
        is the one difference a class name alone cannot express, which is why the theme
        carries a flag for it.
        """
        self.assertTrue(BOOTSTRAP5["clearCloseLabel"])
        self.assertFalse(BOOTSTRAP3["clearCloseLabel"])
        self.assertFalse(BOOTSTRAP4["clearCloseLabel"])

    def test_each_theme_marks_the_popover_distinctly(self):
        """The wrapper class is what the stylesheet hooks onto, so it has to differ."""
        popovers = {name: theme["popover"] for name, theme in THEMES.items()}

        self.assertEqual(len(set(popovers.values())), 3)


class CustomThemeTests(TestCase):
    """A project describing its own design system, so this is not Bootstrap-only."""

    CUSTOM = {"popover": "card", "nextButton": "button is-primary", "prevButton": "button", "closeButton": "delete"}

    @override_settings(TOURGUIDE_THEME="bulma", TOURGUIDE_THEMES={"bulma": CUSTOM})
    def test_a_project_can_define_its_own(self):
        """The theme is data, so a design system that is not Bootstrap needs no code here."""
        self.assertEqual(get_theme(), self.CUSTOM)

    @override_settings(TOURGUIDE_THEMES={"broken": {"nextBtn": "button"}})
    def test_unknown_keys_are_reported(self):
        """A misspelled key would be silently ignored by the adapter, so it is caught here."""
        with self.assertRaises(ImproperlyConfigured) as caught:
            get_theme("broken")

        self.assertIn("nextBtn", str(caught.exception))

    @override_settings(TOURGUIDE_THEMES={"broken": "btn btn-primary"})
    def test_a_theme_that_is_not_a_dict_is_reported(self):
        """Naming the type is more use than the AttributeError it would otherwise become."""
        with self.assertRaises(ImproperlyConfigured) as caught:
            get_theme("broken")

        self.assertIn("dict", str(caught.exception))

    @override_settings(TOURGUIDE_THEMES={"bootstrap5": {"popover": "mine"}})
    def test_a_project_can_replace_a_shipped_theme(self):
        """Project themes are looked up first, so a shipped one can be adjusted by name."""
        self.assertEqual(get_theme("bootstrap5"), {"popover": "mine"})


class ThemeInConfigTests(TestCase):
    """What reaches the client."""

    def setUp(self):
        """A request, since the tag needs one to mint a CSRF token."""
        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()

    def test_config__has_no_theme_by_default(self):
        """Unset means the adapter leaves the popover exactly as driver.js built it."""
        self.assertIsNone(embedded_config(render("{% tourguide %}", request=self.request))["theme"])

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_config__carries_the_resolved_class_map(self):
        """The map is resolved server-side, so the adapter never learns what Bootstrap is."""
        theme = embedded_config(render("{% tourguide %}", request=self.request))["theme"]

        self.assertEqual(theme["nextButton"], "btn btn-primary btn-sm")
        self.assertEqual(theme["closeButton"], "btn-close")

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_tourguide__theme_argument_overrides_the_setting(self):
        """The override reaches the config, not just the resolver."""
        theme = embedded_config(render('{% tourguide theme="bootstrap3" %}', request=self.request))["theme"]

        self.assertEqual(theme["closeButton"], "close")

    def test_config__names_the_classes_the_adapter_swaps(self):
        """The adapter is told which driver.js classes to remove rather than hardcoding them."""
        classes = embedded_config(render("{% tourguide %}", request=self.request))["themeClasses"]

        self.assertEqual(classes["replaced"]["buttons"], "driver-popover-footer-btn")
        self.assertEqual(classes["replaced"]["close"], "driver-popover-close-btn")
        self.assertEqual(classes["close"], "tourguide-close")


class ThemeStylesheetTests(TestCase):
    """The stylesheet, which is only needed when a theme is on."""

    def setUp(self):
        """A request, since the tag needs one to mint a CSRF token."""
        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()

    def test_stylesheet__is_not_loaded_without_a_theme(self):
        """An unthemed page should not pay for CSS that would do nothing."""
        self.assertNotIn("tourguide-themes.css", render("{% tourguide %}", request=self.request))

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_stylesheet__is_loaded_with_a_theme(self):
        """It carries the close button's positioning, which a theme cannot do without."""
        self.assertIn("tourguide-themes.css", render("{% tourguide %}", request=self.request))

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_stylesheet__loads_after_driver_css(self):
        """Order is what lets it override driver.js: the selectors are the same weight."""
        html = render("{% tourguide %}", request=self.request)

        self.assertLess(html.index("vendor/driver.css"), html.index("tourguide-themes.css"))


class ThemeCheckTests(TestCase):
    """The system check, so a broken theme is reported at `manage.py check`."""

    def test_check__is_quiet_when_no_theme_is_configured(self):
        """Not using themes is the default, not a misconfiguration."""
        self.assertEqual(check_theme(None), [])

    @override_settings(TOURGUIDE_THEME="bootstrap5")
    def test_check__is_quiet_for_a_valid_theme(self):
        """A theme that resolves has nothing to report."""
        self.assertEqual(check_theme(None), [])

    @override_settings(TOURGUIDE_THEME="bootstrap6")
    def test_check__reports_an_unknown_theme(self):
        """Otherwise the only symptom is buttons that quietly have no classes on them."""
        errors = check_theme(None)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "tourguide.E001")
        self.assertIn("TOURGUIDE_THEMES", errors[0].hint)
