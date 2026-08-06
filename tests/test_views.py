"""Tests for the JSON contract.

These go through the test client rather than calling the view functions, because most of what
is being asserted (the audience gate, the method restrictions, CSRF) is only real once the
request has been through URL resolution and middleware.
"""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from tourguide.models import Step, Tour
from tourguide.progress.models import TourProgress


class TourListTests(TestCase):
    """The picker's endpoint: which tours a user is offered, and where they got to."""

    @classmethod
    def setUpTestData(cls):
        """One tour of each audience, plus an inactive one, and users to view them as."""
        cls.url = reverse("tourguide:tour-list")
        cls.student = User.objects.create_user("student", password="x")
        cls.teacher = User.objects.create_user("teacher", password="x", is_staff=True)

        cls.open_tour = Tour.objects.create(slug="quests", name="Quests", description="How quests work", icon="fa-scroll", order=0)
        cls.staff_tour = Tour.objects.create(slug="approvals", name="Approvals", audience=Tour.Audience.STAFF, order=1)
        cls.withdrawn = Tour.objects.create(slug="old", name="Old tour", is_active=False, order=2)

    def slugs_for(self, user):
        """The slugs the endpoint offers ``user``, in the order it returns them."""
        self.client.force_login(user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        return [tour["slug"] for tour in response.json()["tours"]]

    def test_tour_list__rejects_anonymous_callers_with_json(self):
        """An anonymous caller is refused in JSON, not redirected to a login page.

        The tour is fetched from a page the user is already on, so a redirect would hand the
        client an HTML login form where it expected a list of tours.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("detail", response.json())

    def test_tour_list__omits_tours_the_user_may_not_see(self):
        """A student is not offered a staff-only tour."""
        self.assertEqual(self.slugs_for(self.student), ["quests"])

    def test_tour_list__includes_staff_tours_for_staff(self):
        """A teacher is offered both, in the tours' own order."""
        self.assertEqual(self.slugs_for(self.teacher), ["quests", "approvals"])

    def test_tour_list__omits_withdrawn_tours(self):
        """An inactive tour is offered to nobody, including staff."""
        self.assertNotIn("old", self.slugs_for(self.teacher))

    def test_tour_list__describes_each_tour(self):
        """Each entry carries what the picker needs to render a row."""
        self.client.force_login(self.student)

        entry = self.client.get(self.url).json()["tours"][0]

        self.assertEqual(entry["slug"], "quests")
        self.assertEqual(entry["name"], "Quests")
        self.assertEqual(entry["description"], "How quests work")
        self.assertEqual(entry["icon"], "fa-scroll")

    def test_tour_list__progress_is_null_when_the_tour_was_never_offered(self):
        """No record means null rather than a zeroed record.

        The absence of a record is what makes a tour start by itself, so this has to be
        distinguishable from a record sitting at step zero.
        """
        self.client.force_login(self.student)

        self.assertIsNone(self.client.get(self.url).json()["tours"][0]["progress"])

    def test_tour_list__reports_progress_when_there_is_some(self):
        """A tour in flight reports how far the user got and that it is unfinished."""
        TourProgress.objects.create(user=self.student, tour_slug="quests", last_step=3)
        self.client.force_login(self.student)

        progress = self.client.get(self.url).json()["tours"][0]["progress"]

        self.assertEqual(progress["last_step"], 3)
        self.assertFalse(progress["is_finished"])
        self.assertIsNone(progress["completed_at"])
        self.assertIsNone(progress["dismissed_at"])
        self.assertIsNotNone(progress["started_at"])

    def test_tour_list__reports_a_finished_tour_as_finished(self):
        """A completed tour carries its completion time and reads as finished."""
        TourProgress.objects.create(user=self.student, tour_slug="quests").mark_completed()
        self.client.force_login(self.student)

        progress = self.client.get(self.url).json()["tours"][0]["progress"]

        self.assertIsNotNone(progress["completed_at"])
        self.assertTrue(progress["is_finished"])

    def test_tour_list__reports_only_this_user_s_progress(self):
        """Another user's progress on the same tour is not reported here."""
        TourProgress.objects.create(user=self.teacher, tour_slug="quests", last_step=5)
        self.client.force_login(self.student)

        self.assertIsNone(self.client.get(self.url).json()["tours"][0]["progress"])

    def test_tour_list__does_not_query_per_tour(self):
        """Progress is fetched in one query for all tours rather than one per tour.

        Guards the reason progress is collected into a dict up front: the obvious version
        issues a query per row, which is the one performance mistake this endpoint could make.
        """
        for index in range(5):
            Tour.objects.create(slug=f"extra-{index}", name=f"Extra {index}", order=10 + index)
        self.client.force_login(self.student)

        # Session, user, the tours, and the progress for all of them.
        with self.assertNumQueries(4):
            self.client.get(self.url)

    def test_tour_list__refuses_a_post(self):
        """The list is a read, so posting to it is not allowed."""
        self.client.force_login(self.student)

        self.assertEqual(self.client.post(self.url).status_code, 405)


class TourSpecTests(TestCase):
    """The spec endpoint: the steps of one tour, ready to run."""

    @classmethod
    def setUpTestData(cls):
        """A tour with a step of each page-reference kind, and a staff-only tour."""
        cls.student = User.objects.create_user("student", password="x")
        cls.teacher = User.objects.create_user("teacher", password="x", is_staff=True)

        cls.tour = Tour.objects.create(slug="quests", name="Quests", description="How quests work")
        cls.url = reverse("tourguide:tour-spec", args=["quests"])
        cls.by_url_name = Step.objects.create(
            tour=cls.tour,
            order=0,
            title="Open the admin",
            content="<b>Here</b>",
            element="#menu",
            side="bottom",
            align="start",
            url_name="admin:index",
        )
        cls.by_path = Step.objects.create(tour=cls.tour, order=1, title="Settings", path="/settings/")
        cls.no_page = Step.objects.create(tour=cls.tour, order=2, title="Stays put")

        cls.staff_tour = Tour.objects.create(slug="approvals", name="Approvals", audience=Tour.Audience.STAFF)
        cls.withdrawn = Tour.objects.create(slug="old", name="Old tour", is_active=False)

    def test_tour_spec__rejects_anonymous_callers(self):
        """A spec is per user, so there is nothing to serve an anonymous caller."""
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_tour_spec__returns_the_steps_in_order(self):
        """Steps arrive in their tour order, which is the order they will be shown in."""
        self.client.force_login(self.student)

        body = self.client.get(self.url).json()

        self.assertEqual(body["slug"], "quests")
        self.assertEqual(body["name"], "Quests")
        self.assertEqual([step["order"] for step in body["steps"]], [0, 1, 2])

    def test_tour_spec__describes_a_step_fully(self):
        """A step carries everything the renderer needs, with nothing left to look up."""
        self.client.force_login(self.student)

        step = self.client.get(self.url).json()["steps"][0]

        self.assertEqual(step["element"], "#menu")
        self.assertEqual(step["title"], "Open the admin")
        self.assertEqual(step["content"], "<b>Here</b>")
        self.assertEqual(step["side"], "bottom")
        self.assertEqual(step["align"], "start")

    def test_tour_spec__reverses_url_names_to_paths(self):
        """URL names are resolved here, so the client never reverses anything.

        The client has no URLconf, which is the whole reason a step may name a route rather
        than a literal path.
        """
        self.client.force_login(self.student)

        steps = self.client.get(self.url).json()["steps"]

        self.assertEqual(steps[0]["path"], "/admin/")
        self.assertEqual(steps[1]["path"], "/settings/")

    def test_tour_spec__path_is_null_for_a_step_with_no_page_of_its_own(self):
        """A step that stays on the current page says so with null rather than a guess."""
        self.client.force_login(self.student)

        self.assertIsNone(self.client.get(self.url).json()["steps"][2]["path"])

    def test_tour_spec__survives_a_url_name_that_no_longer_reverses(self):
        """A renamed route costs one step its navigation, not the whole tour.

        The host project owns its URLconf and can rename a route with nothing written to this
        table, so `update()` is how such a row realistically comes about: it bypasses the
        validation that would otherwise have caught it.
        """
        Step.objects.filter(pk=self.by_url_name.pk).update(url_name="renamed:away")
        self.client.force_login(self.student)

        with self.assertLogs("tourguide.views", level="WARNING") as logs:
            body = self.client.get(self.url).json()

        self.assertEqual([step["order"] for step in body["steps"]], [0, 1, 2])
        self.assertIsNone(body["steps"][0]["path"])
        self.assertIn("renamed:away", logs.output[0])

    def test_tour_spec__is_not_available_to_the_wrong_audience(self):
        """A student asking for a staff tour's spec is refused."""
        self.client.force_login(self.student)

        self.assertEqual(self.client.get(reverse("tourguide:tour-spec", args=["approvals"])).status_code, 404)

    def test_tour_spec__is_available_to_the_right_audience(self):
        """The same request from a teacher succeeds, so the refusal is the audience gate."""
        self.client.force_login(self.teacher)

        self.assertEqual(self.client.get(reverse("tourguide:tour-spec", args=["approvals"])).status_code, 200)

    def test_tour_spec__hides_a_forbidden_tour_the_same_way_as_a_missing_one(self):
        """A forbidden tour is indistinguishable from one that does not exist.

        A 403 on the staff tour would confirm to a student who guessed the slug that a tour by
        that name exists, which turns the endpoint into a way to enumerate the staff-facing
        parts of the site.
        """
        self.client.force_login(self.student)

        forbidden = self.client.get(reverse("tourguide:tour-spec", args=["approvals"]))
        missing = self.client.get(reverse("tourguide:tour-spec", args=["no-such-tour"]))

        self.assertEqual(forbidden.status_code, missing.status_code)
        self.assertEqual(forbidden.json().keys(), missing.json().keys())

    def test_tour_spec__is_not_available_for_a_withdrawn_tour(self):
        """An inactive tour cannot be run by asking for its spec directly."""
        self.client.force_login(self.teacher)

        self.assertEqual(self.client.get(reverse("tourguide:tour-spec", args=["old"])).status_code, 404)

    def test_tour_spec__does_not_query_per_step(self):
        """Steps come back in one query however many there are."""
        for order in range(3, 9):
            Step.objects.create(tour=self.tour, order=order, title=f"Step {order}")
        self.client.force_login(self.student)

        # Session, user, the tour, and its steps.
        with self.assertNumQueries(4):
            self.client.get(self.url)


class RecordProgressTests(TestCase):
    """The progress endpoint: the only write in the contract."""

    @classmethod
    def setUpTestData(cls):
        """A tour to record against, a staff-only tour, and users."""
        cls.student = User.objects.create_user("student", password="x")
        cls.teacher = User.objects.create_user("teacher", password="x", is_staff=True)
        cls.tour = Tour.objects.create(slug="quests", name="Quests")
        cls.staff_tour = Tour.objects.create(slug="approvals", name="Approvals", audience=Tour.Audience.STAFF)
        cls.url = reverse("tourguide:tour-progress", args=["quests"])

    def post(self, payload, url=None):
        """POST ``payload`` as JSON to the progress endpoint."""
        return self.client.post(url or self.url, data=json.dumps(payload), content_type="application/json")

    def test_record_progress__rejects_anonymous_callers(self):
        """There is nowhere to record progress for someone who is not logged in."""
        self.assertEqual(self.post({"action": "step", "step": 1}).status_code, 403)

    def test_record_progress__refuses_a_get(self):
        """Progress is written, not read, so the endpoint takes only POST."""
        self.client.force_login(self.student)

        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_record_progress__requires_a_csrf_token(self):
        """The endpoint is not CSRF-exempt.

        The write is small but real: a forged request could mark a tour dismissed so that it
        never appears for that user again.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.student)

        response = csrf_client.post(self.url, data=json.dumps({"action": "dismissed"}), content_type="application/json")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(TourProgress.objects.exists())

    def test_record_progress__records_a_step(self):
        """Reporting a step stores it and echoes the stored progress back."""
        self.client.force_login(self.student)

        response = self.post({"action": "step", "step": 4})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["progress"]["last_step"], 4)
        self.assertEqual(TourProgress.objects.get(user=self.student, tour_slug="quests").last_step, 4)

    def test_record_progress__marks_a_tour_completed(self):
        """Finishing is recorded as completion, which is distinct from giving up."""
        self.client.force_login(self.student)

        response = self.post({"action": "completed"})

        self.assertTrue(response.json()["progress"]["is_finished"])
        progress = TourProgress.objects.get(user=self.student, tour_slug="quests")
        self.assertIsNotNone(progress.completed_at)
        self.assertIsNone(progress.dismissed_at)

    def test_record_progress__marks_a_tour_dismissed(self):
        """Giving up is recorded separately from finishing."""
        self.client.force_login(self.student)

        self.post({"action": "dismissed"})

        progress = TourProgress.objects.get(user=self.student, tour_slug="quests")
        self.assertIsNotNone(progress.dismissed_at)
        self.assertIsNone(progress.completed_at)

    def test_record_progress__updates_rather_than_duplicating(self):
        """Posting twice for the same tour updates the one record."""
        self.client.force_login(self.student)

        self.post({"action": "step", "step": 1})
        self.post({"action": "step", "step": 5})

        self.assertEqual(TourProgress.objects.filter(user=self.student, tour_slug="quests").count(), 1)
        self.assertEqual(TourProgress.objects.get(user=self.student, tour_slug="quests").last_step, 5)

    def test_record_progress__does_not_rewind(self):
        """The model's forward-only rule is reachable through the endpoint."""
        self.client.force_login(self.student)

        self.post({"action": "step", "step": 5})
        response = self.post({"action": "step", "step": 2})

        self.assertEqual(response.json()["progress"]["last_step"], 5)

    def test_record_progress__is_refused_for_the_wrong_audience(self):
        """A student cannot write progress for a staff-only tour."""
        self.client.force_login(self.student)

        response = self.post({"action": "step", "step": 1}, url=reverse("tourguide:tour-progress", args=["approvals"]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(TourProgress.objects.exists())

    def test_record_progress__is_refused_for_an_unknown_tour(self):
        """A slug naming no tour is refused, and writes nothing."""
        self.client.force_login(self.student)

        response = self.post({"action": "step", "step": 1}, url=reverse("tourguide:tour-progress", args=["no-such-tour"]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(TourProgress.objects.exists())

    def test_record_progress__rejects_a_body_that_is_not_json(self):
        """A malformed body is a client error rather than a crash."""
        self.client.force_login(self.student)

        response = self.client.post(self.url, data="not json", content_type="application/json")

        self.assertEqual(response.status_code, 400)

    def test_record_progress__rejects_a_json_body_that_is_not_an_object(self):
        """A bare JSON value is valid JSON but not a request this endpoint understands."""
        self.client.force_login(self.student)

        self.assertEqual(self.post([1, 2, 3]).status_code, 400)

    def test_record_progress__rejects_an_unknown_action(self):
        """Only the three documented actions are accepted."""
        self.client.force_login(self.student)

        self.assertEqual(self.post({"action": "restart"}).status_code, 400)

    def test_record_progress__rejects_a_missing_action(self):
        """An object with no action is refused rather than defaulting to one."""
        self.client.force_login(self.student)

        self.assertEqual(self.post({"step": 1}).status_code, 400)

    def test_record_progress__rejects_a_step_that_is_not_a_number(self):
        """A step has to be a number, since it is a position in the tour."""
        self.client.force_login(self.student)

        self.assertEqual(self.post({"action": "step", "step": "two"}).status_code, 400)

    def test_record_progress__rejects_a_missing_step(self):
        """The step action needs a step to record."""
        self.client.force_login(self.student)

        self.assertEqual(self.post({"action": "step"}).status_code, 400)

    def test_record_progress__rejects_a_negative_step(self):
        """Positions start at zero, and the column cannot hold a negative anyway."""
        self.client.force_login(self.student)

        self.assertEqual(self.post({"action": "step", "step": -1}).status_code, 400)

    def test_record_progress__rejects_a_boolean_step(self):
        """`true` is an integer in Python and would otherwise be recorded as step 1.

        A caller sending a boolean here has filled in the wrong field, and silently storing
        step 1 would resume them somewhere they never reached.
        """
        self.client.force_login(self.student)

        response = self.post({"action": "step", "step": True})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(TourProgress.objects.exists())

    def test_record_progress__a_rejected_request_creates_no_record(self):
        """A refused request must not leave a progress record behind.

        Creating the record is itself meaningful: a tour starts by itself only while the user
        has no record for it, so a record created while serving a request that then failed
        would quietly stop the tour ever being offered.
        """
        self.client.force_login(self.student)

        self.post({"action": "restart"})
        self.post({"action": "step", "step": "two"})

        self.assertFalse(TourProgress.objects.exists())
