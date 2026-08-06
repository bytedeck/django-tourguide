"""A URLconf with the tour endpoints left out.

Exists so a test can render `{% tourguide %}` in a project that installed the app but never
included its URLs, which is the mistake the tag is supposed to explain rather than blow up on.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
