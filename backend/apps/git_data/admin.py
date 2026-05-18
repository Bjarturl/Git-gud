from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.search.models import Match
from .mixins import ResetProcessedAtMixin

from .models import Commit, Gist, Repo, User, UserRelationship, UserStatus


class LanguageFilter(SimpleListFilter):
    title = "programming language"
    parameter_name = "language"

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT unnest(languages) AS language, COUNT(*) AS count
                FROM git_repo
                WHERE languages != '{}'
                GROUP BY unnest(languages)
                ORDER BY count DESC, language
                LIMIT 50
                """
            )
            lang_counts = [(lang, count)
                           for lang, count in cursor.fetchall() if lang]

        return [
            (lang, f"{lang} ({count})" if i < 50 else lang)
            for i, (lang, count) in enumerate(lang_counts)
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(languages__contains=[self.value()])
        return queryset


class RepoInline(admin.TabularInline):
    model = Repo
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request)

    def has_add_permission(self, request, obj=None):
        return False


class UserRelationshipFromInline(admin.TabularInline):
    model = UserRelationship
    fk_name = "from_user"
    extra = 0
    verbose_name = "Outgoing relationship"
    verbose_name_plural = "Outgoing relationships"

    def has_add_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


class UserRelationshipToInline(admin.TabularInline):
    model = UserRelationship
    fk_name = "to_user"
    extra = 0
    verbose_name = "Incoming relationship"
    verbose_name_plural = "Incoming relationships"

    def has_add_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(User)
class UserAdmin(ResetProcessedAtMixin, admin.ModelAdmin):
    list_display = ["status_actions", "username", "name",
                    "location", "bio"]
    list_display_links = ["username"]
    list_filter = ["account_type", "status",
                   "discovery_method"]
    search_fields = ["username", "name", "email"]
    inlines = [RepoInline, UserRelationshipFromInline,
               UserRelationshipToInline]
    fieldsets = [
        ("Basic Information", {
            "fields": ["username", "account_type", "discovery_method", "status"],
        }),
        ("Profile", {
            "fields": ["name", "email", "avatar", "bio", "company", "location", "url"],
        }),
        ("Source Information", {
            "fields": ["source_user_id", "tags"],
        }),
        ("Timestamps", {
            "fields": ["created_at", "processed_at", "source_created_at"],
            "classes": ["collapse"],
        }),
        ("Matches", {
            "fields": ["matches_table"],
        }),
    ]

    class Media:
        js = ("admin/js/user_status.js",)

    @admin.display(description="Actions")
    def status_actions(self, obj):
        eye_btn = format_html(
            """
            <a href="{}" target="_blank"
            style="display:flex; align-items:center; justify-content:center;
                    text-decoration:none;
                    background:#0d6efd; color:white;
                    width:28px; height:28px; border-radius:4px;">
                👁
            </a>
            """,
            obj.url or "#",
        )

        if obj.status == UserStatus.UNKNOWN:
            return format_html(
                """
                <div style="display: flex; gap: 6px;">
                    <button type="button"
                            class="status-btn confirm-btn"
                            data-user-id="{0}"
                            onclick="confirmUser(this, {0})"
                            style="border:none; background:#28a745; color:white;
                                width:28px; height:28px; border-radius:4px; cursor:pointer;">
                        ✓
                    </button>
                    {1}
                    <button type="button"
                            class="status-btn hide-btn"
                            data-user-id="{0}"
                            onclick="hideUser(this, {0})"
                            style="border:none; background:#dc3545; color:white;
                                width:28px; height:28px; border-radius:4px; cursor:pointer;">
                        ✕
                    </button>
                </div>
                """,
                obj.id,
                eye_btn,
            )
        elif obj.status == UserStatus.HIDDEN:
            return format_html(
                """
                <div style="display: flex; gap: 6px;">
                    <button type="button"
                            class="status-btn confirm-btn"
                            data-user-id="{0}"
                            onclick="confirmUser(this, {0})"
                            style="border:none; background:#28a745; color:white;
                                width:28px; height:28px; border-radius:4px; cursor:pointer;">
                        ✓
                    </button>
                    {1}
                </div>
                """,
                obj.id,
                eye_btn,
            )
        else:
            return format_html(
                '<div style="display: flex; gap: 6px;">{}</div>',
                eye_btn,
            )

    @admin.display(description="Matches")
    def matches_table(self, obj):
        matches = (
            Match.objects
            .filter(Q(commit__author=obj) | Q(gist__author=obj))
            .select_related("regex", "commit", "commit__repo", "gist")
            .order_by("-created_at")[:500]
        )

        if not matches:
            return "No matches found."

        rows = []
        for m in matches:
            if m.commit:
                source = format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    m.commit.url or "#",
                    f"{m.commit.repo.full_name}@{m.commit.sha[:7]}",
                )
            else:
                source = format_html(
                    '<a href="{}" target="_blank">gist:{}</a>',
                    m.gist.url or "#",
                    m.gist.gist_id[:8],
                )

            rows.append(format_html(
                "<tr>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'><code>{}</code></td>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'>{}</td>"
                "</tr>",
                m.regex.name or m.regex.regex_pattern[:40],
                m.match_type,
                m.match[:100],
                m.filename or "—",
                source,
            ))

        header = mark_safe(
            "<thead><tr>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Regex</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Type</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Match</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>File</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Source</th>"
            "</tr></thead>"
        )

        return format_html(
            "<table style='width:100%;border-collapse:collapse'>{}<tbody>{}</tbody></table>",
            header,
            mark_safe("".join(rows)),
        )

    def get_urls(self):
        return [
            path("hide-user/<int:user_id>/",
                 self.hide_user, name="git_data_user_hide"),
            path("confirm-user/<int:user_id>/",
                 self.confirm_user, name="git_data_user_confirm"),
            *super().get_urls(),
        ]

    def _update_user_status(self, request, user_id, status):
        updated = User.objects.filter(id=user_id).update(status=status)
        if not updated:
            return JsonResponse({"success": False, "error": "User not found"})

        return JsonResponse({"success": True})

    def hide_user(self, request, user_id):
        return self._update_user_status(request, user_id, UserStatus.HIDDEN)

    def confirm_user(self, request, user_id):
        return self._update_user_status(request, user_id, UserStatus.CONFIRMED)

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] + ["matches_table"]


@admin.register(Repo)
class RepoAdmin(ResetProcessedAtMixin, admin.ModelAdmin):
    list_display = ["full_name", "owner", "is_fork",
                    "stars", "created_at"]
    list_filter = ["processed_at", "is_fork", LanguageFilter]
    search_fields = ["name", "full_name", "owner__username", "description"]
    date_hierarchy = "created_at"

    fieldsets = [
        ("Basic Information", {
            "fields": ["name", "full_name", "owner"],
        }),
        ("Repository Details", {
            "fields": [
                "description",
                "default_branch",
                "url",
                "homepage",
                "is_fork",
                "languages",
            ],
        }),
        ("Statistics", {
            "fields": ["stars", "size"],
        }),
        ("Source Information", {
            "fields": ["source_repo_id", "tags"],
        }),
        ("Timestamps", {
            "fields": ["created_at", "processed_at", "source_created_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Commit)
class CommitAdmin(ResetProcessedAtMixin, admin.ModelAdmin):
    list_display = ["sha", "repo", "author",
                    "branch_name", "commit_date"]
    list_filter = ["processed_at"]
    search_fields = ["sha", "message", "author__username", "repo__full_name"]
    date_hierarchy = "commit_date"
    list_per_page = 100
    list_select_related = ("repo", "author", "committer")

    fieldsets = [
        ("Commit Information", {
            "fields": ["sha", "repo", "author", "committer"],
        }),
        ("Commit Details", {
            "fields": ["message", "url", "commit_date", "branch_name", "pr_number"],
        }),
        ("Statistics", {
            "fields": ["additions", "deletions"],
        }),
        ("Timestamps", {
            "fields": ["created_at", "processed_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("repo", "author", "committer")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Gist)
class GistAdmin(ResetProcessedAtMixin, admin.ModelAdmin):
    list_display = ["gist_id", "revision_id",
                    "author", "description", "source_created_at"]
    list_filter = ["processed_at"]
    search_fields = ["gist_id", "description", "author__username", "filenames"]
    date_hierarchy = "source_created_at"

    fieldsets = [
        ("Gist Information", {
            "fields": ["gist_id", "revision_id", "author"],
        }),
        ("Content", {
            "fields": ["url", "description", "filenames"],
        }),
        ("Timestamps", {
            "fields": ["created_at", "processed_at", "source_created_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(UserRelationship)
class UserRelationshipAdmin(admin.ModelAdmin):
    list_display = ["from_user", "to_user",
                    "relationship_type", "repo", "created_at"]
    list_filter = ["relationship_type"]
    search_fields = ["from_user__username",
                     "to_user__username", "repo__full_name"]
    date_hierarchy = "created_at"
    list_per_page = 100
    list_max_show_all = 500

    fieldsets = [
        ("Relationship", {
            "fields": ["from_user", "to_user", "relationship_type"],
        }),
        ("Context", {
            "fields": ["repo"],
        }),
        ("Timestamps", {
            "fields": ["created_at"],
            "classes": ["collapse"],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
