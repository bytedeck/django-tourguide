"""Database-driven, multi-page guided tours for Django.

This package ships two Django apps:

``tourguide``
    The tour definitions: the ``Tour`` and ``Step`` models, the JSON endpoints, the template
    tags, and the renderer.

``tourguide.progress``
    Per-user progress: the ``TourProgress`` model.

They are separate apps so that a django-tenants project can keep one shared copy of the
tour definitions in the public schema while tracking progress per tenant. An ordinary
single-tenant project lists both in ``INSTALLED_APPS`` and can ignore the distinction.
"""

__version__ = "0.1.0"
