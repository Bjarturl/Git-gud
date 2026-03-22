from django.contrib import admin
from .models import RawEvent


@admin.register(RawEvent)
class RawEventAdmin(admin.ModelAdmin):
    list_display = ("repo_id", "sha_hex", "observed_at")
    list_filter = ("observed_at",)
    search_fields = ("repo_id",)
    ordering = ("-observed_at",)

    def sha_hex(self, obj):
        return obj.sha.hex()
    sha_hex.short_description = "SHA"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.defer("sha")
