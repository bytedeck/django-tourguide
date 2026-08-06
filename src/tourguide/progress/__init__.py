"""Per-user tour progress.

Kept in its own Django app so that a django-tenants project can place it in ``TENANT_APPS``
while the definitions in ``tourguide`` stay in ``SHARED_APPS``. Progress has to live with the
tenant because it will foreign-key the tenant's user table.

The ``TourProgress`` model itself is added in a later release.
"""
