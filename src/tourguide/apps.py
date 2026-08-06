from django.apps import AppConfig


class TourguideConfig(AppConfig):
    """The tour definitions app, holding the ``Tour`` and ``Step`` models.

    Under django-tenants this app belongs in ``SHARED_APPS`` only, so that a single copy of
    the tours lives in the public schema. It must not also appear in ``TENANT_APPS``: an app
    named in both gets its tables built in both, and the empty per-tenant copy would then
    shadow the populated public one through the search path.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "tourguide"
    verbose_name = "Tour Guide"
