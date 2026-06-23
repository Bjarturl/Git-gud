import re
from io import BytesIO

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils.html import format_html
from openpyxl import Workbook

from apps.git_data.models import Tag
from .models import Match, MatchStatus, Regex

_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _safe(value):
    if not value:
        return ""
    return _ILLEGAL_CHARS_RE.sub("", str(value))


class MatchInline(admin.TabularInline):
    model = Match
    extra = 0
    fields = [
        "created_at",
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


class DeletedFilter(admin.SimpleListFilter):
    title = "deleted"
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return [("yes", "Deleted"), ("no", "Active")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(deleted_in_commit__isnull=False) | queryset.filter(deleted_in_gist__isnull=False)
        if self.value() == "no":
            return queryset.filter(deleted_in_commit__isnull=True, deleted_in_gist__isnull=True)
        return queryset


class AuthorFilter(admin.SimpleListFilter):
    title = "author"
    parameter_name = "author"
    template = "admin/search/match/username_filter.html"

    def lookups(self, request, model_admin):
        return [("_", "_")]

    def choices(self, changelist):
        yield {
            "selected": bool(self.value()),
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": "All",
        }

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        return queryset.filter(
            Q(commit__author__username__iexact=val) | Q(gist__author__username__iexact=val)
        )


class RepoOwnerFilter(admin.SimpleListFilter):
    title = "repo owner"
    parameter_name = "repo_owner"
    template = "admin/search/match/username_filter.html"

    def lookups(self, request, model_admin):
        return [("_", "_")]

    def choices(self, changelist):
        yield {
            "selected": bool(self.value()),
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": "All",
        }

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        return queryset.filter(
            Q(commit__repo__owner__username__iexact=val) | Q(repo__owner__username__iexact=val)
        )


class MatchStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return MatchStatus.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class AuthorTagFilter(SimpleListFilter):
    title = "author tag"
    parameter_name = "author_tag"

    def lookups(self, request, model_admin):
        return Tag.objects.values_list("name", "name")

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        return queryset.filter(
            Q(commit__author__tags__name=self.value()) |
            Q(gist__author__tags__name=self.value())
        ).distinct()


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):

    list_display = [
        "status_actions",
        "regex",
        "match_preview",
        "duplicate_count",
        "author_link",
        "repo_link",
        "source_link",
        "deleted_link",
    ]
    list_display_links = ["regex"]
    list_filter = [
        AuthorFilter,
        RepoOwnerFilter,
        AuthorTagFilter,
        DeletedFilter,
        MatchStatusFilter,
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
    list_select_related = [
        "regex",
        "commit", "commit__repo", "commit__author",
        "gist", "gist__author",
        "deleted_in_commit", "deleted_in_gist",
    ]
    date_hierarchy = "created_at"
    list_per_page = 100

    class Media:
        js = ("admin/js/match_status.js",)

    fieldsets = [
        ("Pattern", {
            "fields": ["regex"],
        }),
        ("Source", {
            "fields": ["commit", "gist", "filename"],
        }),
        ("Matched Content", {
            "fields": ["match", "raw_match"],
        }),
        ("Deletion", {
            "fields": ["deleted_in_commit", "deleted_in_gist"],
        }),
        ("Timestamps", {
            "fields": ["created_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        url_name = getattr(request.resolver_match, "url_name", "")
        if url_name.endswith("_changelist"):
            dup_count = Match.objects.filter(
                match=OuterRef("match")
            ).values("match").annotate(c=Count("id")).values("c")
            qs = qs.annotate(_duplicate_count=Subquery(dup_count, output_field=IntegerField()))
        return qs

    @admin.display(description="Dupes", ordering="_duplicate_count")
    def duplicate_count(self, obj):
        return obj._duplicate_count

    @admin.display(description="Actions")
    def status_actions(self, obj):
        if obj.status == MatchStatus.FALSE_POSITIVE:
            return format_html(
                """
                <button type="button"
                        data-match-pk="{0}"
                        onclick="markInteresting(this, {0})"
                        style="border:none;background:#ffc107;color:white;
                               width:28px;height:28px;border-radius:4px;cursor:pointer;">
                    ★
                </button>
                """,
                obj.id,
            )
        if obj.status == MatchStatus.INTERESTING:
            return format_html(
                """
                <button type="button"
                        data-match-pk="{0}"
                        onclick="markFalsePositive(this, {0})"
                        style="border:none;background:#dc3545;color:white;
                               width:28px;height:28px;border-radius:4px;cursor:pointer;">
                    ✕
                </button>
                """,
                obj.id,
            )
        return format_html(
            """
            <div data-match-pk="{0}" style="display:flex;gap:6px;">
                <button type="button"
                        onclick="markInteresting(this, {0})"
                        style="border:none;background:#ffc107;color:white;
                               width:28px;height:28px;border-radius:4px;cursor:pointer;">
                    ★
                </button>
                <button type="button"
                        onclick="markFalsePositive(this, {0})"
                        style="border:none;background:#dc3545;color:white;
                               width:28px;height:28px;border-radius:4px;cursor:pointer;">
                    ✕
                </button>
            </div>
            """,
            obj.id,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel),
                name="matches_export_excel",
            ),
            path(
                "mark-match/<int:match_id>/false-positive/",
                self.admin_site.admin_view(self.mark_false_positive),
                name="search_match_false_positive",
            ),
            path(
                "mark-match/<int:match_id>/interesting/",
                self.admin_site.admin_view(self.mark_interesting),
                name="search_match_interesting",
            ),
        ]
        return custom_urls + urls

    def _mark_match_status(self, request, match_id, status):
        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist:
            return JsonResponse({"success": False, "error": "Match not found"})
        qs = Match.objects.filter(match=match.match)
        ids = list(qs.values_list("id", flat=True))
        qs.update(status=status)
        return JsonResponse({"success": True, "count": len(ids), "match": match.match, "ids": ids})

    def mark_false_positive(self, request, match_id):
        return self._mark_match_status(request, match_id, MatchStatus.FALSE_POSITIVE)

    def mark_interesting(self, request, match_id):
        return self._mark_match_status(request, match_id, MatchStatus.INTERESTING)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["export_excel_url"] = "export-excel/"
        return super().changelist_view(request, extra_context=extra_context)

    def _apply_export_filters(self, request, queryset):
        for filter_class in [AuthorFilter, RepoOwnerFilter, DeletedFilter, MatchStatusFilter, SourceTypeFilter]:
            f = filter_class(request, request.GET.copy(), Match, self)
            queryset = f.queryset(request, queryset)
        category = request.GET.get("regex__category")
        if category:
            queryset = queryset.filter(regex__category=category)
        is_active = request.GET.get("regex__is_active")
        if is_active in ("1", "0"):
            queryset = queryset.filter(regex__is_active=is_active == "1")
        return queryset

    def export_excel(self, request):
        queryset = Match.objects.exclude(status=MatchStatus.FALSE_POSITIVE)
        queryset = self._apply_export_filters(request, queryset)
        queryset = queryset.select_related(
            "regex",
            "commit",
            "commit__repo",
            "commit__repo__owner",
            "commit__author",
            "gist",
            "gist__author",
        ).order_by("id")

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
                _safe(obj.regex.category) if obj.regex_id else "",
                _safe(obj.raw_match),
                _safe(obj.match),
                _safe(html_url),
                _safe(user),
                _safe(user_company),
                _safe(repo),
                _safe(commit_message),
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

    @admin.display(description="Author")
    def author_link(self, obj):
        if obj.commit_id and obj.commit.author_id:
            return format_html(
                '<a href="/admin/git_data/user/{}/change/">{}</a>',
                obj.commit.author_id,
                obj.commit.author.username,
            )
        if obj.gist_id and obj.gist.author_id:
            return format_html(
                '<a href="/admin/git_data/user/{}/change/">{}</a>',
                obj.gist.author_id,
                obj.gist.author.username,
            )
        return "—"

    @admin.display(description="Repo")
    def repo_link(self, obj):
        if obj.commit_id and obj.commit.repo_id:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.commit.repo.url or "#",
                obj.commit.repo.full_name,
            )
        if obj.gist_id:
            return "gist"
        return "—"

    @admin.display(description="Source")
    def source_link(self, obj):
        if obj.commit_id:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.commit.url or "#",
                obj.commit.sha[:7],
            )
        if obj.gist_id:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.gist.url or "#",
                obj.gist.gist_id[:8],
            )
        return "—"

    @admin.display(description="Deleted in")
    def deleted_link(self, obj):
        if obj.deleted_in_commit_id:
            return format_html(
                '<a href="{}" target="_blank" style="color:#6c757d">{}</a>',
                obj.deleted_in_commit.url or "#",
                obj.deleted_in_commit.sha[:7],
            )
        if obj.deleted_in_gist_id:
            return format_html(
                '<a href="{}" target="_blank" style="color:#6c757d">{}</a>',
                obj.deleted_in_gist.url or "#",
                obj.deleted_in_gist.gist_id[:8],
            )
        return "—"

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

    filter_horizontal = ("tags",)
    fieldsets = [
        ("Pattern", {
            "fields": ["name", "regex_pattern", "category", "is_active"],
        }),
        ("Tag Scope", {
            "fields": ["tags"],
            "description": "Leave empty to run on all users. Select tags to restrict this regex to users with those tags only.",
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
