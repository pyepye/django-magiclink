from django.contrib import admin
from django.utils import timezone

from .models import MagicLink, MagicLinkUnsubscribe


class StatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [("live", "Live"), ("expired", "Expired"), ("disabled", "Disabled")]

    def queryset(self, request, queryset):
        if self.value() == "live":
            return queryset.filter(disabled=False, expiry__gt=timezone.now())
        if self.value() == "expired":
            return queryset.filter(disabled=False, expiry__lte=timezone.now())
        if self.value() == "disabled":
            return queryset.filter(disabled=True)
        return queryset


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ("email", "ip_address", "created", "expiry", "status", "times_used")
    list_filter = (StatusFilter, "created")
    search_fields = ("email", "ip_address")
    date_hierarchy = "created"
    ordering = ("-created",)
    # token and cookie_value are not listed: anyone who can read them can log in
    fields = (
        "email",
        "ip_address",
        "created",
        "expiry",
        "redirect_url",
        "disabled",
        "times_used",
    )
    readonly_fields = ("created",)
    actions = ("unsubscribe",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_unsubscribe_permission(self, request):
        return request.user.has_perm("magiclink.add_magiclinkunsubscribe")

    @admin.display(description="Status")
    def status(self, obj):
        if obj.disabled:
            return "Disabled"
        return "Live" if obj.expiry > timezone.now() else "Expired"

    @admin.action(
        description="Unsubscribe the selected email addresses",
        permissions=["unsubscribe"],
    )
    def unsubscribe(self, request, queryset):
        emails = set(queryset.values_list("email", flat=True))
        existing = MagicLinkUnsubscribe.objects.filter(email__in=emails)
        new_emails = emails.difference(existing.values_list("email", flat=True))
        MagicLinkUnsubscribe.objects.bulk_create(
            MagicLinkUnsubscribe(email=email) for email in new_emails
        )
        self.message_user(request, f"{len(new_emails)} email addresses unsubscribed")


@admin.register(MagicLinkUnsubscribe)
class MagicLinkUnsubscribeAdmin(admin.ModelAdmin):
    list_display = ("email",)
    search_fields = ("email",)
    ordering = ("email",)
