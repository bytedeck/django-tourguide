"""Database-driven, multi-page guided tours for Django.

This package ships two Django apps:

``tourguide``
    The tour definitions. Will hold the ``Tour`` and ``Step`` models.

``tourguide.progress``
    Per-user progress. Will hold the ``TourProgress`` model.

They are separate apps so that a django-tenants project can keep one shared copy of the
tour definitions in the public schema while tracking progress per tenant. An ordinary
single-tenant project lists both in ``INSTALLED_APPS`` and can ignore the distinction.

Both apps are currently empty: the models, endpoints, and renderer arrive before 0.1.0.
"""

__version__ = "0.1.0.dev0"
