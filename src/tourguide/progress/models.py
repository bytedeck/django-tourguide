"""Per-user tour progress.

Separate from the tour definitions so that a django-tenants project can keep this app in
``TENANT_APPS`` while ``tourguide`` sits in ``SHARED_APPS``: progress belongs to the tenant
because it references the tenant's users, while the tours themselves are the same everywhere.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class TourProgress(models.Model):
    """How far one user has got through one tour.

    A tour is referenced by **slug rather than foreign key**. That is what allows the
    definitions to live in a different schema, and it is the right call regardless: shipped
    tour content gets re-imported whenever it changes, and a real foreign key would
    cascade-delete everyone's progress each time. The trade is that nothing at the database
    level guarantees the named tour exists, so :attr:`tour` may be ``None``.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tour_progress",
    )
    tour_slug = models.SlugField(
        max_length=100,
        help_text="Slug of the tour this progress belongs to. Not a foreign key: the tour may live in another schema.",
    )
    last_step = models.PositiveIntegerField(
        default=0,
        help_text="Order of the step the user last reached, so a tour spanning several pages can resume.",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the user reached the end of the tour.",
    )
    dismissed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the user closed the tour early. Kept separate from completion, since finishing and giving up are different outcomes.",
    )

    class Meta:
        verbose_name_plural = "tour progress"
        ordering = ["user", "tour_slug"]
        constraints = [
            models.UniqueConstraint(fields=["user", "tour_slug"], name="tourguide_progress_one_record_per_user_and_tour"),
        ]

    def __str__(self):
        return f"{self.user} / {self.tour_slug}"

    @property
    def tour(self):
        """The :class:`~tourguide.models.Tour` this progress refers to, or ``None``.

        ``None`` means the tour has been deleted or renamed since this record was written.
        Callers are expected to treat that as "nothing to show" rather than an error, because
        it is a normal consequence of referring to the tour by slug.

        Not cached: a request that resolves this usually does so once, and caching would make
        a long-lived instance serve a stale tour after content is re-imported.
        """
        from tourguide.models import Tour

        return Tour.objects.filter(slug=self.tour_slug).first()

    @property
    def is_finished(self):
        """Whether the user is done with this tour, by either completing or dismissing it.

        This is the question the auto-start check asks: a tour should not reappear because the
        user gave up on it rather than reaching the end.
        """
        return self.completed_at is not None or self.dismissed_at is not None

    def record_step(self, step_order):
        """Record that the user reached the step at ``step_order``.

        Only ever moves forward. Stepping backwards through a tour is normal, and letting it
        rewind the stored position would resume someone earlier than they actually got.
        """
        if step_order > self.last_step:
            self.last_step = step_order
            self.save(update_fields=["last_step"])

    def mark_completed(self):
        """Record that the user reached the end of the tour.

        Idempotent: the first completion time is kept, since a repeat run should not rewrite
        when the tour was originally finished.
        """
        if self.completed_at is None:
            self.completed_at = timezone.now()
            self.save(update_fields=["completed_at"])

    def mark_dismissed(self):
        """Record that the user closed the tour early.

        Idempotent for the same reason as :meth:`mark_completed`.
        """
        if self.dismissed_at is None:
            self.dismissed_at = timezone.now()
            self.save(update_fields=["dismissed_at"])
