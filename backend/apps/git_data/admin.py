from io import BytesIO

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db import connection
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from openpyxl import Workbook

from apps.search.models import Match, MatchStatus
from apps.task_queue.backends import enqueue

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


class RelatedToFilter(SimpleListFilter):
    title = "related to"
    parameter_name = "related_to"
    template = "admin/git_data/user/related_to_filter.html"

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
        related_user = User.objects.filter(username__iexact=val).first()
        if not related_user:
            return queryset.none()
        return queryset.filter(
            Q(outgoing_relationships__to_user=related_user) |
            Q(incoming_relationships__from_user=related_user)
        ).distinct()


class ScannedFilter(SimpleListFilter):
    title = "scanned"
    parameter_name = "scanned"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(scanned_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(scanned_at__isnull=True)
        return queryset


class HasMatchesFilter(SimpleListFilter):
    title = "has matches"
    parameter_name = "has_matches"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        if self.value() not in ("yes", "no"):
            return queryset
        has_match = Exists(
            Match.objects.filter(
                Q(commit__author=OuterRef("pk")) | Q(gist__author=OuterRef("pk"))
            )
        )
        if self.value() == "yes":
            return queryset.filter(has_match)
        return queryset.filter(~has_match)


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
class UserAdmin(admin.ModelAdmin):
    list_display = ["status_actions", "username", "name",
                    "company", "location", "bio"]
    list_display_links = ["username"]
    list_filter = ["account_type", "status", "discovery_method", ScannedFilter, HasMatchesFilter, RelatedToFilter]
    search_fields = ["username", "name", "email", "company", "bio", "location"]
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
            "fields": ["created_at", "processed_at", "scanned_at", "source_created_at"],
            "classes": ["collapse"],
        }),
        ("Matches", {
            "fields": ["matches_table", "match_admin_link"],
        }),
    ]

    class Media:
        js = ("admin/js/user_status.js", "admin/js/match_status.js")

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
        pipeline_btn = format_html(
            """
            <button type="button"
                    onclick="runPipeline(this, {})"
                    style="border:none; background:#17a2b8; color:white;
                           width:28px; height:28px; border-radius:4px; cursor:pointer;">
                ▶
            </button>
            """,
            obj.id,
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
                    {2}
                </div>
                """,
                obj.id,
                eye_btn,
                pipeline_btn,
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
                    {2}
                </div>
                """,
                obj.id,
                eye_btn,
                pipeline_btn,
            )
        else:
            return format_html(
                '<div style="display: flex; gap: 6px;">{}{}</div>',
                eye_btn,
                pipeline_btn,
            )

    @admin.display(description="Matches")
    def matches_table(self, obj):
        select = (
            "regex",
            "commit", "commit__repo", "commit__author",
            "gist", "gist__author",
            "deleted_in_commit", "deleted_in_commit__repo",
            "deleted_in_gist",
        )
        own = list(
            Match.objects
            .filter(Q(commit__author=obj) | Q(gist__author=obj))
            .exclude(status=MatchStatus.FALSE_POSITIVE)
            .select_related(*select)
            .order_by("regex__name")[:250]
        )
        repo_matches = list(
            Match.objects
            .filter(commit__repo__owner=obj)
            .exclude(commit__author=obj)
            .exclude(status=MatchStatus.FALSE_POSITIVE)
            .select_related(*select)
            .order_by("regex__name")[:250]
        )
        matches = own + repo_matches

        if not matches:
            return "No matches found."

        rows = []
        for m in matches:
            if m.commit:
                repo_cell = format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    m.commit.repo.url or "#",
                    m.commit.repo.full_name,
                )
                source = format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    m.commit.url or "#",
                    m.commit.sha[:7],
                )
                committer = (
                    format_html(
                        '<a href="/admin/git_data/user/{}/change/">{}</a>',
                        m.commit.author_id,
                        m.commit.author.username,
                    )
                    if m.commit.author_id else "—"
                )
            else:
                repo_cell = "—"
                source = format_html(
                    '<a href="{}" target="_blank">gist:{}</a>',
                    m.gist.url or "#",
                    m.gist.gist_id[:8],
                )
                committer = (
                    format_html(
                        '<a href="/admin/git_data/user/{}/change/">{}</a>',
                        m.gist.author_id,
                        m.gist.author.username,
                    )
                    if m.gist.author_id else "—"
                )

            if m.deleted_in_commit_id:
                deleted = format_html(
                    '<a href="{}" target="_blank" style="color:#6c757d">{}</a>',
                    m.deleted_in_commit.url or "#",
                    m.deleted_in_commit.sha[:7],
                )
            elif m.deleted_in_gist_id:
                deleted = format_html(
                    '<a href="{}" target="_blank" style="color:#6c757d">gist:{}</a>',
                    m.deleted_in_gist.url or "#",
                    m.deleted_in_gist.gist_id[:8],
                )
            else:
                deleted = "—"

            actions = format_html(
                "<td style='padding:4px 8px;white-space:nowrap'>"
                "<button type='button' onclick=\"markMatchByUrl(this,'/admin/search/match/mark-match/{0}/interesting/',false)\""
                " style='border:none;background:#ffc107;color:white;width:24px;height:24px;border-radius:3px;cursor:pointer;margin-right:3px;'>★</button>"
                "<button type='button' onclick=\"markMatchByUrl(this,'/admin/search/match/mark-match/{0}/false-positive/',true)\""
                " style='border:none;background:#6c757d;color:white;width:24px;height:24px;border-radius:3px;cursor:pointer;font-size:9px;font-weight:bold;'>FP</button>"
                "</td>",
                m.id,
            )
            rows.append(format_html(
                "<tr>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'><code style='word-break:break-all'>{}</code></td>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'>{}</td>"
                "<td style='padding:4px 8px'>{}</td>"
                "{}</tr>",
                m.regex.name or m.regex.regex_pattern[:40],
                m.match[:100],
                repo_cell,
                m.filename or "—",
                committer,
                source,
                deleted,
                actions,
            ))

        header = mark_safe(
            "<thead><tr>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Regex</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Match</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Repo</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>File</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Committer</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Source</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Deleted in</th>"
            "<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'></th>"
            "</tr></thead>"
        )

        return format_html(
            "<table style='width:100%;border-collapse:collapse;margin-top:8px'>{}<tbody>{}</tbody></table>",
            header,
            mark_safe("".join(rows)),
        )

    @admin.display(description="")
    def match_admin_link(self, obj):
        return format_html(
            '<a href="/admin/search/match/?author_id={}">View all matches in Match admin →</a>',
            obj.pk,
        )

    def get_urls(self):
        return [
            path("hide-user/<int:user_id>/",
                 self.hide_user, name="git_data_user_hide"),
            path("confirm-user/<int:user_id>/",
                 self.confirm_user, name="git_data_user_confirm"),
            path("run-pipeline-ajax/<int:user_id>/",
                 self.admin_site.admin_view(self.run_pipeline_ajax),
                 name="git_data_user_run_pipeline_ajax"),
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel),
                name="git_data_user_export_excel",
            ),
            path(
                "<int:user_id>/run-pipeline/",
                self.admin_site.admin_view(self.run_pipeline),
                name="git_data_user_run_pipeline",
            ),
            *super().get_urls(),
        ]

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        try:
            user = User.objects.get(pk=object_id)
            if user.status == UserStatus.CONFIRMED:
                extra_context["action_buttons"] = [
                    {
                        "url": f"/admin/git_data/user/{object_id}/run-pipeline/",
                        "title": "Run Pipeline",
                        "style": "background-color: #0d6efd; color: white; border-radius: 4px; padding: 8px 16px; text-decoration: none; font-weight: bold; margin-bottom: 12px; display: inline-block;",
                    }
                ]
        except User.DoesNotExist:
            pass
        return super().change_view(request, object_id, form_url, extra_context)

    def run_pipeline_ajax(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            job = enqueue(
                "apps.task_queue.tasks.pipeline_task",
                priority=0,
                name=f"full user scan - {user.username}",
                username=user.username,
            )
            return JsonResponse({
                "success": True,
                "job_id": str(job.id),
                "job_url": f"/admin/task_queue/taskjob/{job.id}/change/",
                "username": user.username,
            })
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "User not found"})
        except Exception as exc:
            return JsonResponse({"success": False, "error": str(exc)})

    def run_pipeline(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            job = enqueue(
                "apps.task_queue.tasks.pipeline_task",
                priority=0,
                name=f"full user scan - {user.username}",
                username=user.username,
            )
            messages.success(
                request,
                mark_safe(
                    f'Pipeline started for "{user.username}" — '
                    f'<a href="/admin/task_queue/taskjob/{job.id}/change/">View job {job.id}</a>'
                ),
            )
        except User.DoesNotExist:
            messages.error(request, "User not found")
        except Exception as exc:
            messages.error(request, f"Failed to start pipeline: {exc}")

        return HttpResponseRedirect(f"/admin/git_data/user/{user_id}/change/")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["export_excel_url"] = "export-excel/"
        return super().changelist_view(request, extra_context=extra_context)

    def export_excel(self, request):
        queryset = self.get_queryset(request).order_by("id")

        wb = Workbook()
        ws = wb.active
        ws.title = "Users"

        ws.append([
            "username",
            "name",
            "email",
            "company",
            "location",
            "bio",
            "url",
            "account_type",
            "status",
            "discovery_method",
            "created_at",
        ])

        for obj in queryset.iterator():
            ws.append([
                obj.username,
                obj.name or "",
                obj.email or "",
                obj.company or "",
                obj.location or "",
                obj.bio or "",
                obj.url or "",
                obj.account_type,
                obj.status,
                obj.discovery_method,
                obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if obj.created_at else "",
            ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="users.xlsx"'
        return response

    def _update_user_status(self, request, user_id, status):
        updated = User.objects.filter(id=user_id).update(status=status)
        if not updated:
            return JsonResponse({"success": False, "error": "User not found"})

        return JsonResponse({"success": True})

    def hide_user(self, request, user_id):
        return self._update_user_status(request, user_id, UserStatus.HIDDEN)

    def confirm_user(self, request, user_id):
        return self._update_user_status(request, user_id, UserStatus.CONFIRMED)

    def get_list_display(self, request):
        fields = list(super().get_list_display(request))
        if request.GET.get("has_matches") == "yes" and "match_count" not in fields:
            fields.append("match_count")
        return fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get("has_matches") == "yes":
            commit_matches = Subquery(
                Match.objects.filter(commit__author=OuterRef("pk"))
                .values("commit__author")
                .annotate(c=Count("id"))
                .values("c")[:1],
                output_field=IntegerField(),
            )
            gist_matches = Subquery(
                Match.objects.filter(gist__author=OuterRef("pk"))
                .values("gist__author")
                .annotate(c=Count("id"))
                .values("c")[:1],
                output_field=IntegerField(),
            )
            qs = qs.annotate(
                _match_count=Coalesce(commit_matches, 0) + Coalesce(gist_matches, 0)
            )
        return qs

    @admin.display(description="Matches", ordering="_match_count")
    def match_count(self, obj):
        return obj._match_count

    def get_readonly_fields(self, request, obj=None):
        editable = {"processed_at"}
        return [
            field.name for field in self.model._meta.fields
            if field.name not in editable
        ] + ["matches_table", "match_admin_link"]


@admin.register(Repo)
class RepoAdmin(admin.ModelAdmin):
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

    def get_urls(self):
        custom_urls = [
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel),
                name="git_data_repo_export_excel",
            ),
        ]
        return custom_urls + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["export_excel_url"] = "export-excel/"
        return super().changelist_view(request, extra_context=extra_context)

    def export_excel(self, request):
        queryset = (
            self.get_queryset(request)
            .select_related("owner")
            .order_by("id")
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Repos"

        ws.append([
            "full_name",
            "owner",
            "description",
            "url",
            "homepage",
            "is_fork",
            "languages",
            "stars",
            "size",
            "default_branch",
            "created_at",
        ])

        for obj in queryset.iterator():
            ws.append([
                obj.full_name,
                obj.owner.username if obj.owner_id else "",
                obj.description or "",
                obj.url or "",
                obj.homepage or "",
                obj.is_fork,
                ", ".join(obj.languages) if obj.languages else "",
                obj.stars or 0,
                obj.size or 0,
                obj.default_branch or "",
                obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if obj.created_at else "",
            ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="repos.xlsx"'
        return response

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
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
class GistAdmin(admin.ModelAdmin):
    list_display = ["gist_id", "revision_id",
                    "author", "description", "is_fork", "source_created_at"]
    list_filter = ["processed_at", "is_fork"]
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
