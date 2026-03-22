from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Match, Regex
from io import BytesIO

from django.http import HttpResponse
from django.urls import path
from openpyxl import Workbook


class MatchInline(admin.TabularInline):
    model = Match
    extra = 0
    fields = [
        "created_at",
        "match_type",
        "filename",
        "match_preview",
        "source_link",
    ]
    readonly_fields = fields
    show_change_link = True
    can_delete = False

    @admin.display(description="Match")
    def match_preview(self, obj):
        if not obj.match:
            return ""
        return obj.match[:120] + ("..." if len(obj.match) > 120 else "")

    @admin.display(description="Source")
    def source_link(self, obj):
        if obj.commit_id:
            url = f"/admin/git_data/commit/{obj.commit_id}/change/"
            label = f"Commit {obj.commit.sha[:8]}"
            return format_html('<a href="{}">{}</a>', url, label)

        if obj.gist_id:
            url = f"/admin/git_data/gist/{obj.gist_id}/change/"
            label = f"Gist {obj.gist.gist_id[:8]}"
            return format_html('<a href="{}">{}</a>', url, label)

        return "-"

    def has_add_permission(self, request, obj=None):
        return False


class SourceTypeFilter(admin.SimpleListFilter):
    title = "source type"
    parameter_name = "source_type"

    def lookups(self, request, model_admin):
        return [
            ("commit", "Commit"),
            ("gist", "Gist"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "commit":
            return queryset.filter(commit__isnull=False)
        if self.value() == "gist":
            return queryset.filter(gist__isnull=False)
        return queryset


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "regex",
        "source_type",
        "match_type",
        "match_preview",
    ]
    list_filter = [
        "match_type",
        "regex__category",
        "regex__is_active",
        SourceTypeFilter,
        "created_at",
    ]
    search_fields = [
        "match",
        "raw_match",
        "filename",
        "regex__name",
        "regex__regex_pattern",
        "commit__sha",
        "commit__message",
        "commit__repo__full_name",
        "gist__gist_id",
        "gist__description",
    ]
    autocomplete_fields = ["regex", "commit", "gist"]
    list_select_related = ["regex", "commit",
                           "gist", "commit__repo", "gist__author"]
    date_hierarchy = "created_at"
    list_per_page = 100

    fieldsets = [
        ("Pattern", {
            "fields": ["regex", "match_type"],
        }),
        ("Source", {
            "fields": ["commit", "gist", "filename"],
        }),
        ("Matched Content", {
            "fields": ["match", "raw_match"],
        }),
        ("Timestamps", {
            "fields": ["created_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel),
                name="matches_export_excel",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["export_excel_url"] = "export-excel/"
        return super().changelist_view(request, extra_context=extra_context)

    def export_excel(self, request):
        queryset = (
            self.get_queryset(request)
            .select_related(
                "regex",
                "commit",
                "commit__repo",
                "commit__repo__owner",
                "commit__author",
                "gist",
                "gist__author",
            )
            .order_by("id")
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Matches"

        ws.append([
            "category",
            "raw_match",
            "matching_line",
            "html_url",
            "user",
            "user_company",
            "repo",
            "commit_message",
        ])

        for obj in queryset.iterator():
            if obj.commit_id:
                user = obj.commit.author.username if obj.commit.author_id else ""
                user_company = obj.commit.author.company if obj.commit.author_id else ""
                html_url = obj.commit.url or ""
                repo = obj.commit.repo.full_name if obj.commit.repo_id else ""
                commit_message = obj.commit.message or ""
            elif obj.gist_id:
                user = obj.gist.author.username if obj.gist.author_id else ""
                user_company = obj.gist.author.company if obj.gist.author_id else ""
                html_url = obj.gist.url or ""
                repo = ""
                commit_message = ""
            else:
                user = ""
                user_company = ""
                html_url = ""
                repo = ""
                commit_message = ""

            ws.append([
                str(obj.regex.category) if obj.regex_id else "",
                obj.raw_match or "",
                obj.match or "",
                html_url,
                user,
                user_company,
                repo,
                commit_message,
            ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="matches.xlsx"'
        return response

    @admin.display(description="Source type")
    def source_type(self, obj):
        if obj.commit_id:
            return "Commit"
        if obj.gist_id:
            return "Gist"
        return "-"

    @admin.display(description="Source")
    def source_object(self, obj):
        if obj.commit_id:
            url = f"/admin/git_data/commit/{obj.commit_id}/change/"
            label = obj.commit.sha[:8]
            repo = obj.commit.repo.full_name if obj.commit.repo_id else ""
            return format_html('<a href="{}">{} {}</a>', url, repo, label)

        if obj.gist_id:
            url = f"/admin/git_data/gist/{obj.gist_id}/change/"
            label = obj.gist.gist_id[:8]
            return format_html('<a href="{}">{}</a>', url, label)

        return "-"

    @admin.display(description="Match")
    def match_preview(self, obj):
        if not obj.match:
            return ""
        return obj.match[:100] + ("..." if len(obj.match) > 100 else "")

    @admin.display(description="Raw line")
    def raw_match_preview(self, obj):
        if not obj.raw_match:
            return ""
        return obj.raw_match[:140] + ("..." if len(obj.raw_match) > 140 else "")

    def get_readonly_fields(self, request, obj=None):
        return ["created_at"]


@admin.register(Regex)
class RegexAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "is_active",
        "total_matches",
        "commit_matches",
        "gist_matches",
        "created_at",
        "updated_at",
    ]
    list_filter = ["is_active", "category", "created_at", "updated_at"]
    search_fields = ["name", "regex_pattern"]
    ordering = ["category", "name"]
    inlines = [MatchInline]

    fieldsets = [
        ("Pattern", {
            "fields": ["name", "regex_pattern", "category", "is_active"],
        }),
        ("Timestamps", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _total_matches=Count("matches", distinct=True),
                _commit_matches=Count("matches__commit", distinct=True),
                _gist_matches=Count("matches__gist", distinct=True),
            )
        )

    @admin.display(ordering="_total_matches", description="Total matches")
    def total_matches(self, obj):
        return obj._total_matches

    @admin.display(ordering="_commit_matches", description="Commit matches")
    def commit_matches(self, obj):
        return obj._commit_matches

    @admin.display(ordering="_gist_matches", description="Gist matches")
    def gist_matches(self, obj):
        return obj._gist_matches

    def get_readonly_fields(self, request, obj=None):
        return ["created_at", "updated_at"]


class SourceTypeFilter(admin.SimpleListFilter):
    title = "source type"
    parameter_name = "source_type"

    def lookups(self, request, model_admin):
        return [
            ("commit", "Commit"),
            ("gist", "Gist"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "commit":
            return queryset.filter(commit__isnull=False)
        if self.value() == "gist":
            return queryset.filter(gist__isnull=False)
        return queryset
