from django.contrib import messages
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.urls import path, reverse


class ResetProcessedAtMixin:
    change_list_template = "admin/reset_processed_at_changelist.html"

    def get_urls(self):
        return [
            path(
                "reset-processed-at/",
                self.admin_site.admin_view(self.reset_processed_at),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_reset_processed_at",
            ),
            *super().get_urls(),
        ]

    def changelist_view(self, request, extra_context=None):
        opts = self.model._meta
        extra_context = extra_context or {}
        extra_context["reset_processed_at_url"] = (
            reverse(
                f"admin:{opts.app_label}_{opts.model_name}_reset_processed_at")
            + ("?" + request.GET.urlencode() if request.GET else "")
        )
        return super().changelist_view(request, extra_context=extra_context)



    def reset_processed_at(self, request):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        updated = queryset.update(processed_at=None)

        self.message_user(
            request,
            f"{updated} rows updated.",
            level=messages.SUCCESS,
        )

        url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
        )
        if request.GET:
            url += "?" + request.GET.urlencode()
        return HttpResponseRedirect(url)