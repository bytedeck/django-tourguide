"""The tour definitions: what a tour is, and what its steps point at.

These are the models a host project edits to build a tour. They deliberately hold no
per-user state, which is what allows them to live in a shared schema under django-tenants
while progress is tracked per tenant (see ``tourguide.progress``).
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import NoReverseMatch, reverse


class Tour(models.Model):
    """A named sequence of steps that walks a user through part of a site.

    A tour is identified by its ``slug`` rather than its primary key, because progress
    records refer to it by slug and may live in a different schema.
    """

    class Audience(models.TextChoices):
        """Who a tour is offered to."""

        EVERYONE = "everyone", "Everyone"
        STAFF = "staff", "Staff only"
        SUPERUSER = "superuser", "Superusers only"

    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Stable identifier used in URLs and in progress records. Changing it orphans existing progress.",
    )
    name = models.CharField(max_length=100, help_text="Shown to the user when choosing a tour.")
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="One line on what this tour covers, shown alongside the name.",
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional icon, interpreted by the host project (a CSS class, an emoji, whatever it renders).",
    )
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.EVERYONE,
        help_text="Who is offered this tour. Enforced server-side, not just in the picker.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to withdraw the tour without deleting it or anyone's progress.",
    )
    order = models.PositiveIntegerField(default=0, help_text="Sort order when several tours are offered.")

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def is_visible_to(self, user):
        """Return whether ``user`` may be offered this tour.

        Anonymous users are never offered a tour, since progress is per user and there is
        nowhere to record it.
        """
        if not self.is_active:
            return False
        if user is None or not user.is_authenticated:
            return False
        if self.audience == self.Audience.SUPERUSER:
            return bool(user.is_superuser)
        if self.audience == self.Audience.STAFF:
            # Superusers are not necessarily flagged as staff in every project, so treat
            # either flag as satisfying a staff-only tour.
            return bool(user.is_staff or user.is_superuser)
        return True


class Step(models.Model):
    """One stop in a tour: what to point at, what to say, and which page to say it on.

    A step with no ``element`` renders as a centred box with no anchor, which is how a tour
    opens, closes, or says something not tied to a particular control.
    """

    class Side(models.TextChoices):
        """Which side of the target element the popover sits on."""

        TOP = "top", "Top"
        RIGHT = "right", "Right"
        BOTTOM = "bottom", "Bottom"
        LEFT = "left", "Left"
        OVER = "over", "Over the element"

    class Align(models.TextChoices):
        """How the popover lines up along the chosen side."""

        START = "start", "Start"
        CENTER = "center", "Center"
        END = "end", "End"

    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveIntegerField(default=0, help_text="Position within the tour. Steps are shown in this order.")
    element = models.CharField(
        max_length=255,
        blank=True,
        help_text="CSS selector for the element to highlight. Leave blank for a centred step with no anchor.",
    )
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField(blank=True, help_text="The body of the step. HTML is allowed.")
    side = models.CharField(max_length=10, choices=Side.choices, blank=True, help_text="Leave blank to let the renderer decide.")
    align = models.CharField(max_length=10, choices=Align.choices, blank=True, help_text="Leave blank to let the renderer decide.")
    url_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Django URL name of the page this step lives on, for example 'quests:quests'. "
        "Preferred over a literal path, since it survives URL restructuring.",
    )
    url_args = models.JSONField(
        default=list,
        blank=True,
        help_text="Positional arguments for the URL name, if it takes any.",
    )
    path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Literal relative path, for example '/settings/'. Use only for pages with no URL name. "
        "Must not include a scheme or host, so that the tour works on any domain.",
    )

    class Meta:
        ordering = ["tour", "order"]
        constraints = [
            models.UniqueConstraint(fields=["tour", "order"], name="tourguide_step_unique_order_per_tour"),
        ]

    def __str__(self):
        return f"{self.tour} ({self.order})"

    def clean(self):
        """Validate the page this step belongs to.

        Catches the two mistakes that would otherwise only show up as a broken tour in the
        browser: naming both a URL name and a path, and naming a URL that does not resolve.
        """
        errors = {}

        if self.url_name and self.path:
            errors["path"] = "Set either a URL name or a path, not both."

        if self.url_name:
            try:
                reverse(self.url_name, args=self.url_args or [])
            except NoReverseMatch:
                errors["url_name"] = f"'{self.url_name}' does not reverse to a URL. Check the name and any arguments."

        if self.path:
            if "://" in self.path or self.path.startswith("//"):
                # An absolute URL would pin the tour to one domain, which breaks
                # subdomain-per-tenant setups and any non-production environment.
                errors["path"] = "Enter a relative path with no scheme or host."
            elif not self.path.startswith("/"):
                errors["path"] = "Enter a path starting with '/'."

        if errors:
            raise ValidationError(errors)

    def get_path(self):
        """Return the path this step lives on, or ``None`` if it is not page-specific.

        A step with neither a URL name nor a path belongs to whatever page the tour is
        already on, which is the common case for consecutive steps.
        """
        if self.url_name:
            return reverse(self.url_name, args=self.url_args or [])
        return self.path or None
