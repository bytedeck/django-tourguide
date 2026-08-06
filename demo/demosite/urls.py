"""URLs for the demo project.

Two content pages rather than one, so that later phases have somewhere for a multi-page tour
to navigate between.
"""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="demo/home.html"), name="home"),
    path("settings/", TemplateView.as_view(template_name="demo/settings.html"), name="settings"),
]
