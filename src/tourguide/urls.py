"""URL patterns for the JSON endpoints.

Include them under whatever prefix the host project prefers:

    path("tourguide/", include("tourguide.urls")),

The prefix is the host project's choice, so the client is told where these live rather than
assuming: nothing in this package hardcodes the mount point.
"""

from django.urls import path

from . import views

app_name = "tourguide"

urlpatterns = [
    path("", views.tour_list, name="tour-list"),
    path("<slug:slug>/spec/", views.tour_spec, name="tour-spec"),
    path("<slug:slug>/progress/", views.record_progress, name="tour-progress"),
]
