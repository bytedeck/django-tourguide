"""URLs for the demo project.

Two content pages rather than one, so that later phases have somewhere for a multi-page tour
to navigate between.
"""

from django.contrib import admin
from django.urls import include, path

from .views import DemoPage

urlpatterns = [
    path("admin/", admin.site.urls),
    path("tourguide/", include("tourguide.urls")),
    path("", DemoPage.as_view(template_name="demo/home.html"), name="home"),
    path("settings/", DemoPage.as_view(template_name="demo/settings.html"), name="settings"),
]
