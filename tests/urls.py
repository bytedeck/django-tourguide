"""URL configuration for the test suite.

The admin is included so that tests have a URL name which genuinely reverses, which is what
`Step.url_name` validation needs to be tested against. Later phases add the tour endpoints
here as they are introduced.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
