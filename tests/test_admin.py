"""Tests for the tour-building admin.

The admin is the authoring interface this package ships, so these exercise it through the
test client rather than calling the `ModelAdmin` methods directly: a broken `list_display`
entry only shows up when the page actually renders.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tourguide.models import Step, Tour


class TourAdminTests(TestCase):
    """The tour changelist and change form."""

    @classmethod
    def setUpTestData(cls):
        """A superuser to browse the admin with, and a tour that has steps."""
        cls.superuser = User.objects.create_superuser("root", "root@example.com", "x")
        cls.tour = Tour.objects.create(slug="quests", name="Quests", description="How quests work")
        Step.objects.create(tour=cls.tour, order=0, title="First", element="#quests-menu")
        Step.objects.create(tour=cls.tour, order=1, title="Second", url_name="admin:index")

    def setUp(self):
        """Browse as a superuser."""
        self.client.force_login(self.superuser)

    def test_changelist__renders_with_step_count(self):
        """The changelist renders and shows how many steps each tour has."""
        response = self.client.get(reverse("admin:tourguide_tour_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quests")
        # The annotated count, via the `step_count` display method.
        self.assertEqual(response.context["cl"].result_list[0]._step_count, 2)

    def test_changelist__step_count_is_annotated_not_per_row(self):
        """The count comes from an annotation, so listing tours does not query per row.

        Guards the reason `get_queryset` is overridden at all: without it, rendering the
        count would issue one query per tour.
        """
        Tour.objects.create(slug="second", name="Second tour")

        with self.assertNumQueries(5):
            # Session, user, count for pagination, full count, and the result list itself.
            # The point is that adding a second tour does not add a query.
            self.client.get(reverse("admin:tourguide_tour_changelist"))

    def test_change_form__renders_with_steps_inline(self):
        """The change form renders with its steps editable inline."""
        response = self.client.get(reverse("admin:tourguide_tour_change", args=[self.tour.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#quests-menu")

    def test_add_form__renders(self):
        """A tour can be started from scratch, which is the authoring entry point."""
        response = self.client.get(reverse("admin:tourguide_tour_add"))

        self.assertEqual(response.status_code, 200)


class StepAdminTests(TestCase):
    """The standalone step admin, used to search steps across tours."""

    @classmethod
    def setUpTestData(cls):
        """A superuser and steps of each page-reference kind."""
        cls.superuser = User.objects.create_superuser("root", "root@example.com", "x")
        cls.tour = Tour.objects.create(slug="t", name="Tour")
        cls.by_url_name = Step.objects.create(tour=cls.tour, order=0, title="Named", url_name="admin:index")
        cls.by_path = Step.objects.create(tour=cls.tour, order=1, title="Literal", path="/settings/")
        cls.no_page = Step.objects.create(tour=cls.tour, order=2, title="Stays put")

    def setUp(self):
        """Browse as a superuser."""
        self.client.force_login(self.superuser)

    def test_changelist__shows_resolved_page_for_each_step(self):
        """The `page` column resolves URL names, shows literal paths, and dashes the rest."""
        response = self.client.get(reverse("admin:tourguide_step_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/admin/")
        self.assertContains(response, "/settings/")

    def test_page_column__is_a_dash_when_step_has_no_page(self):
        """A step with no page of its own reads as a dash rather than blank or None."""
        from tourguide.admin import StepAdmin

        self.assertEqual(StepAdmin.page(None, self.no_page), "-")

    def test_changelist__survives_a_stored_url_name_that_no_longer_resolves(self):
        """A step whose URL name has stopped resolving must not 500 the whole changelist.

        The host project owns its URLconf and can rename a route at any time, invalidating
        stored steps with no write to this table. `update()` reproduces that here because it
        bypasses validation, which is also how such a row gets stored in the first place.
        """
        Step.objects.filter(pk=self.by_url_name.pk).update(url_name="renamed:away")

        response = self.client.get(reverse("admin:tourguide_step_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "unresolved: renamed:away")
        # The other rows still render, so one bad step does not hide the rest.
        self.assertContains(response, "/settings/")

    def test_search__finds_steps_by_selector(self):
        """Steps are searchable by selector, which is how you find what a rename would break."""
        Step.objects.create(tour=self.tour, order=3, title="Target", element="#quests-menu")

        response = self.client.get(reverse("admin:tourguide_step_changelist"), {"q": "quests-menu"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)
