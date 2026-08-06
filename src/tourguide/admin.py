"""Admin for building tours.

This is the tour builder: everything needed to author a tour is editable here, so a host
project gets an authoring interface without writing one.
"""

from django.contrib import admin
from django.db.models import Count

from .models import Step, Tour


class StepInline(admin.StackedInline):
    """Steps edited in place on the tour they belong to.

    Stacked rather than tabular because ``content`` is a text area, which is unusable at
    tabular width.
    """

    model = Step
    extra = 1
    ordering = ["order"]
    fields = ["order", "element", "title", "content", ("side", "align"), ("url_name", "url_args"), "path"]


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    """Tours, with their steps inline."""

    inlines = [StepInline]
    list_display = ["name", "slug", "audience", "is_active", "order", "step_count"]
    list_filter = ["is_active", "audience"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["order", "name"]

    def get_queryset(self, request):
        """Annotate the step count so the list does not run a query per row."""
        return super().get_queryset(request).annotate(_step_count=Count("steps"))

    @admin.display(description="Steps", ordering="_step_count")
    def step_count(self, obj):
        """The number of steps in this tour, for the changelist."""
        return obj._step_count


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    """Steps on their own.

    Most editing happens through the inline on ``Tour``. This exists for searching across
    tours, which is how you find every step pointing at an element you are about to rename.
    """

    list_display = ["tour", "order", "title", "element", "page"]
    list_filter = ["tour"]
    search_fields = ["title", "content", "element", "url_name", "path"]
    ordering = ["tour", "order"]

    @admin.display(description="Page")
    def page(self, obj):
        """The path this step lives on, or a dash when it stays on the current page."""
        return obj.get_path() or "-"
