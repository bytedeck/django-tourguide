"""URL configuration for the test suite.

The admin is included so that tests have a URL name which genuinely reverses, which is what
`Step.url_name` validation needs to be tested against. The tour endpoints are mounted under a
prefix rather than at the root, since that is how a host project includes them and it keeps
the tests honest about the paths being relative to wherever they are mounted.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("tourguide/", include("tourguide.urls")),
]
