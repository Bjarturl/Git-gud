from datetime import datetime, timezone
import json

from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import GitHubToken
from clients.github import GitHubAPIClient


@admin.register(GitHubToken)
class GitHubTokenAdmin(admin.ModelAdmin):
    list_display = ["label", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["label"]
    readonly_fields = ["created_at", "updated_at", "live_rate_limit_display"]

    fieldsets = (
        ("Token Information", {
            "fields": ("label", "token", "is_active"),
        }),
        ("Live GitHub Rate Limits", {
            "fields": ("live_rate_limit_display",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["activate_tokens", "deactivate_tokens"]

    IMPORTANT_RESOURCES = ("search", "code_search", "graphql")

    def live_rate_limit_display(self, obj):
        if not obj:
            return ""

        if not obj.token or not obj.is_active:
            return self._render_info("Token inactive or not configured")

        client = GitHubAPIClient()
        rate_limit_data = client.get_rate_limit_info(obj)

        if "error" in rate_limit_data:
            return self._render_error(
                title="GitHub API Error:",
                message=rate_limit_data.get("error", "Unknown error"),
                details=rate_limit_data.get("message", ""),
            )

        try:
            rate_info = rate_limit_data.get("rate", {})
            resources = rate_limit_data.get("resources", {})

            if not rate_info:
                return self._render_info("No rate limit data available")

            summary_html = self._render_core_rate_summary(rate_info)
            resources_html = format_html_join(
                "",
                "{}",
                (
                    (self._render_resource_card(name, resources[name]),)
                    for name in self.IMPORTANT_RESOURCES
                    if name in resources and resources[name].get("limit", 0) > 0
                ),
            )
            raw_json_html = self._render_raw_json(rate_limit_data)

            return format_html(
                """
                <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif;">
                    {}
                    {}
                    {}
                </div>
                """,
                summary_html,
                resources_html,
                raw_json_html,
            )
        except Exception as exc:
            return self._render_error(
                title="Error parsing rate limit data:",
                message=str(exc),
            )

    live_rate_limit_display.short_description = "GitHub Rate Limits (Live)"

    def _render_info(self, message):
        return format_html(
            """
            <div style="color: #fff; font-style: italic; padding: 15px;">
                {}
            </div>
            """,
            message,
        )

    def _render_error(self, title, message, details=""):
        details_html = format_html(
            '<div style="margin-top: 5px; color: #fff; font-size: 12px;">{}</div>',
            details,
        ) if details else ""

        return format_html(
            """
            <div style="background: #fff5f5; border-left: 4px solid #dc3545; padding: 15px; border-radius: 4px;">
                <strong style="color: #dc3545;">{}</strong>
                <div style="margin-top: 8px; color: #fff; font-family: monospace;">{}</div>
                {}
            </div>
            """,
            title,
            message,
            details_html,
        )

    def _status_meta(self, remaining, limit):
        if remaining == 0:
            return {
                "color": "#dc3545",
                "icon": "🔴",
                "text": "RATE LIMITED",
            }
        if limit and remaining < (limit * 0.3):
            return {
                "color": "#fd7e14",
                "icon": "🟡",
                "text": "LOW",
            }
        return {
            "color": "#28a745",
            "icon": "🟢",
            "text": "OK",
        }

    def _render_core_rate_summary(self, rate_info):
        remaining = rate_info.get("remaining", 0)
        limit = rate_info.get("limit", 0)
        reset_timestamp = rate_info.get("reset", 0)

        reset_time = (
            datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
            if reset_timestamp
            else None
        )
        reset_label = (
            reset_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            if reset_time
            else "Unknown"
        )

        status = self._status_meta(remaining, limit)

        return format_html(
            """
            <div style="margin-bottom: 15px;">
                <div style="background: {}15; border-left: 4px solid {}; padding: 12px; border-radius: 4px; margin-bottom: 10px;">
                    <div style="font-size: 16px; font-weight: bold; color: {};">
                        {} Core API: {}
                    </div>
                    <div style="margin-top: 6px; font-family: monospace; color: #fff;">
                        {}/{} requests remaining
                    </div>
                    <div style="font-size: 12px; color: #fff; margin-top: 4px;">
                        Resets: {}
                    </div>
                </div>
            </div>
            """,
            status["color"],
            status["color"],
            status["color"],
            status["icon"],
            status["text"],
            remaining,
            limit,
            reset_label,
        )

    def _render_resource_card(self, resource_name, resource):
        remaining = resource.get("remaining", 0)
        limit = resource.get("limit", 0)
        status = self._status_meta(remaining, limit)

        return format_html(
            """
            <div style="background: {}15; border-left: 3px solid {}; padding: 8px; margin: 4px 0; border-radius: 4px;">
                <span style="font-weight: bold; color: {};">
                    {} {}
                </span>
                <span style="margin-left: 15px; font-family: monospace; color: #fff;">
                    {}/{}
                </span>
            </div>
            """,
            status["color"],
            status["color"],
            status["color"],
            status["icon"],
            resource_name.replace("_", " ").title(),
            remaining,
            limit,
        )

    def _render_raw_json(self, data):
        formatted_json = json.dumps(data, indent=2)

        return format_html(
            """
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; font-weight: bold; color: #0066cc; margin-bottom: 10px;">
                    Raw JSON Response
                </summary>
                <pre style="border: 1px solid #dee2e6; border-radius: 6px; padding: 15px; font-size: 11px; line-height: 1.4; overflow-x: auto; color: #fff; white-space: pre-wrap;">{}</pre>
            </details>
            """,
            formatted_json,
        )

    def activate_tokens(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} tokens activated successfully.")

    activate_tokens.short_description = "Activate selected tokens"

    def deactivate_tokens(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request, f"{updated} tokens deactivated successfully.")

    deactivate_tokens.short_description = "Deactivate selected tokens"
