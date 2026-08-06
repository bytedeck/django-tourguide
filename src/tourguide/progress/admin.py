"""Admin for inspecting tour progress.

Read-only on purpose. Progress is a record of what a user actually did, so editing it by hand
would falsify that record. It is exposed because "has this person been offered the tour yet,
and where did they stop?" is the first question asked when someone reports a tour behaving
oddly, and answering it otherwise means a shell.
"""

from django.contrib import admin

from .models import TourProgress


@admin.register(TourProgress)
class TourProgressAdmin(admin.ModelAdmin):
    """Per-user progress, listed and filterable but not editable."""

    list_display = ["user", "tour_slug", "last_step", "outcome", "started_at"]
    list_filter = ["tour_slug", "completed_at", "dismissed_at"]
    search_fields = ["user__username", "tour_slug"]
    ordering = ["-started_at"]
    list_select_related = ["user"]

    def has_add_permission(self, request):
        """Progress is written by the tour, never by hand."""
        return False

    def has_change_permission(self, request, obj=None):
        """Progress is a record of what happened, so it is not editable."""
        return False

    @admin.display(description="Outcome")
    def outcome(self, obj):
        """Whether the user finished, gave up, or is still going.

        Completion and dismissal are stored as separate timestamps, so this collapses them
        into the single word a human actually wants to read.
        """
        if obj.completed_at:
            return "completed"
        if obj.dismissed_at:
            return "dismissed"
        return "in progress"
