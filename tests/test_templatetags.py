"""Tests for the template tags.

These render templates rather than calling the tag functions, because what the tags produce is
markup and the interesting failures (a config that will not parse, a slug that escapes its
attribute) only appear once it has been rendered.
"""

import json
import re

from django.contrib.auth.models import AnonymousUser, User
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from tourguide.templatetags.tourguide import SLUG_PLACEHOLDER


def render(source, **context):
    """Render a template fragment with the tag library loaded."""
    return Template("{% load tourguide %}" + source).render(Context(context))


def embedded_config(html):
    """Pull the config back out of rendered markup, the way the client does."""
    match = re.search(r'<script id="tourguide-config" type="application/json">(.*?)</script>', html, re.DOTALL)
    assert match, f"no config element in: {html}"
    # `json_script` escapes for HTML, and the browser's JSON.parse sees the unescaped text.
    text = match.group(1).replace("\\u003C", "<").replace("\\u003E", ">").replace("\\u0026", "&")
    return json.loads(text)


class TourguideTagTests(TestCase):
    """The loader tag, which is the whole client-side entry point."""

    def setUp(self):
        """A request, since the tag needs one to mint a CSRF token."""
        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()

    def test_tourguide__loads_driver_and_the_adapter(self):
        """Both scripts and both stylesheets are emitted, so a page needs nothing else."""
        html = render("{% tourguide %}", request=self.request)

        self.assertIn("tourguide/vendor/driver.js.iife.js", html)
        self.assertIn("tourguide/vendor/driver.css", html)
        self.assertIn("tourguide/tourguide.js", html)
        self.assertIn("tourguide/tourguide.css", html)

    def test_tourguide__defers_both_scripts(self):
        """Deferring keeps them out of the parser's way and fixes their order.

        The adapter looks for driver.js as soon as it runs, so it has to run second.
        """
        html = render("{% tourguide %}", request=self.request)

        self.assertEqual(html.count("defer"), 2)
        self.assertLess(html.index("driver.js.iife.js"), html.index("tourguide/tourguide.js"))

    def test_tourguide__config_carries_the_endpoints(self):
        """The client is told where the endpoints are rather than assuming a mount point."""
        config = embedded_config(render("{% tourguide %}", request=self.request))

        self.assertEqual(config["endpoints"]["list"], reverse("tourguide:tour-list"))
        self.assertEqual(config["endpoints"]["spec"], reverse("tourguide:tour-spec", args=[SLUG_PLACEHOLDER]))
        self.assertEqual(config["endpoints"]["progress"], reverse("tourguide:tour-progress", args=[SLUG_PLACEHOLDER]))

    def test_tourguide__spec_url_is_a_pattern_the_client_can_fill_in(self):
        """The spec URL contains the placeholder, which is how the client builds a real one."""
        config = embedded_config(render("{% tourguide %}", request=self.request))

        self.assertIn(config["slugPlaceholder"], config["endpoints"]["spec"])
        self.assertEqual(
            config["endpoints"]["spec"].replace(config["slugPlaceholder"], "quests"),
            reverse("tourguide:tour-spec", args=["quests"]),
        )

    def test_tourguide__carries_a_csrf_token(self):
        """The progress endpoint is a POST, so the client needs a token to call it.

        Taken from the request rather than the cookie, so it still works under
        `CSRF_USE_SESSIONS`, where there is no cookie to read.
        """
        config = embedded_config(render("{% tourguide %}", request=self.request))

        self.assertTrue(config["csrfToken"])

    def test_tourguide__autostarts_by_default(self):
        """A tour the user has never been offered opens by itself unless told otherwise."""
        config = embedded_config(render("{% tourguide %}", request=self.request))

        self.assertTrue(config["autostart"])

    def test_tourguide__autostart_can_be_switched_off(self):
        """A project that only wants tours on request can say so."""
        config = embedded_config(render("{% tourguide autostart=False %}", request=self.request))

        self.assertFalse(config["autostart"])

    def test_tourguide__renders_without_a_request(self):
        """A template rendered outside a request still loads, just without a token.

        The `request` context processor is not mandatory, and failing to render an entire page
        because of a missing token would be a worse outcome than a tour that cannot post.
        """
        config = embedded_config(render("{% tourguide %}"))

        self.assertEqual(config["csrfToken"], "")

    def test_tourguide__config_is_escaped_not_interpolated(self):
        """The config goes through `json_script`, so it cannot break out of its tag.

        Guards the reason the template uses `json_script` rather than writing the JSON
        directly: a value containing markup would otherwise close the script element.
        """
        html = render("{% tourguide %}", request=self.request)

        body = re.search(r'type="application/json">(.*?)</script>', html, re.DOTALL).group(1)
        self.assertNotIn("<", body)


class TourguideUnmountedTests(TestCase):
    """What happens when the app is installed but its URLs are not included."""

    @override_settings(ROOT_URLCONF="tests.urls_without_tourguide")
    def test_tourguide__explains_that_the_urls_are_not_included(self):
        """The error names the fix, rather than surfacing a bare NoReverseMatch.

        Installing the app and forgetting the URLconf is an easy mistake, and the failure
        otherwise appears deep inside template rendering with no hint of the cause.
        """
        from django.core.exceptions import ImproperlyConfigured

        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        with self.assertRaises(ImproperlyConfigured) as caught:
            render("{% tourguide %}", request=request)

        self.assertIn("include('tourguide.urls')", str(caught.exception))


class TourguideButtonTagTests(TestCase):
    """The convenience button for starting a named tour."""

    def test_tourguide_button__carries_the_slug_the_client_binds_to(self):
        """The client binds to the data attribute, so that is what has to be right."""
        html = render('{% tourguide_button "quests" %}')

        self.assertIn('data-tourguide-start="quests"', html)

    def test_tourguide_button__has_a_default_label(self):
        """The common case needs no label, since there is only one sensible one."""
        self.assertIn("Take the tour", render('{% tourguide_button "quests" %}'))

    def test_tourguide_button__label_can_be_set(self):
        """A project with its own wording can pass it in."""
        html = render('{% tourguide_button "quests" "Show me around" %}')

        self.assertIn("Show me around", html)
        self.assertNotIn("Take the tour", html)

    def test_tourguide_button__class_can_be_replaced(self):
        """The class is a hook rather than a requirement, so a project can use its own."""
        html = render('{% tourguide_button "quests" "Go" css_class="btn btn-primary" %}')

        self.assertIn('class="btn btn-primary"', html)
        self.assertNotIn("tourguide-button", html)

    def test_tourguide_button__is_a_button_not_a_submit(self):
        """Inside a form, a button without an explicit type would submit it."""
        self.assertIn('type="button"', render('{% tourguide_button "quests" %}'))

    def test_tourguide_button__escapes_its_values(self):
        """Values reach the template as ordinary variables, so they are escaped."""
        html = render('{% tourguide_button "quests" label %}', label='<script>alert(1)</script>')

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class TourguideRenderedPageTests(TestCase):
    """The tag as a page actually uses it, loaded once in a base template."""

    def test_tourguide__renders_inside_a_full_page(self):
        """A realistic template renders without the tag needing anything else in context."""
        User.objects.create_user("student", password="x")
        self.client.login(username="student", password="x")

        html = render(
            "<html><body>{% tourguide %}</body></html>",
            request=RequestFactory().get("/"),
        )

        self.assertIn("<html><body>", html)
        self.assertIn("tourguide-config", html)
