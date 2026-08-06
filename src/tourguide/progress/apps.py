from django.apps import AppConfig


class TourguideProgressConfig(AppConfig):
    """The per-user progress app, which will hold the ``TourProgress`` model.

    Under django-tenants this app belongs in ``TENANT_APPS`` only, because ``TourProgress``
    foreign-keys the user model and each tenant schema has its own users.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "tourguide.progress"
    # Django would otherwise derive the label from the last component of `name`, giving a
    # generic "progress" that is likely to collide in a host project and produces opaque
    # table names.
    label = "tourguide_progress"
    verbose_name = "Tour Guide progress"
