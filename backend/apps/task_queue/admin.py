import os
import signal
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Exists, OuterRef
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe

from apps.task_queue.backends import enqueue
from apps.task_queue.models import TaskWorker, TaskWorkerStatus
from apps.git_data.models import Commit, Gist, Repo, User, UserStatus
from apps.events.models import RawEvent
from apps.search.models import Match, Regex
from .forms import AddTaskForm

from .models import TaskJob, TaskJobStatus


@admin.register(TaskWorker)
class TaskWorkerAdmin(admin.ModelAdmin):
    list_display = [
        "worker_name",
        "queue_name",
        "status",
        "pid",
        "hostname",
        "current_job",
        "heartbeat_age",
        "stop_requested",
    ]
    list_filter = ["queue_name", "status", "stop_requested"]
    search_fields = ["worker_name", "hostname", "pid"]
    readonly_fields = [
        "id",
        "worker_name",
        "queue_name",
        "hostname",
        "pid",
        "status",
        "current_job",
        "heartbeat_at",
        "started_at",
        "stopped_at",
        "last_seen_error",
    ]
    actions = ["request_stop", "kill_worker", "mark_dead"]

    @admin.display(description="Heartbeat age")
    def heartbeat_age(self, obj):
        if not obj.heartbeat_at:
            return "-"
        delta = timezone.now() - obj.heartbeat_at
        return f"{int(delta.total_seconds())}s"

    @admin.action(description="Request soft stop")
    def request_stop(self, request, queryset):
        updated = queryset.update(
            stop_requested=True,
            status=TaskWorkerStatus.STOPPING,
        )
        self.message_user(
            request,
            f"Requested stop for {updated} worker(s)",
            messages.WARNING,
        )

    @admin.action(description="Kill worker process")
    def kill_worker(self, request, queryset):
        killed = 0
        for worker in queryset:
            if not worker.pid:
                continue
            try:
                os.kill(worker.pid, signal.SIGTERM)
                killed += 1
            except (ProcessLookupError, PermissionError, OSError):
                pass

        self.message_user(
            request,
            f"Sent SIGTERM to {killed} worker(s)",
            messages.WARNING,
        )

    @admin.action(description="Mark worker dead")
    def mark_dead(self, request, queryset):
        updated = queryset.update(
            status=TaskWorkerStatus.DEAD,
            current_job=None,
            stopped_at=timezone.now(),
        )
        self.message_user(
            request,
            f"Marked {updated} worker(s) dead",
            messages.WARNING,
        )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TaskJob)
class TaskJobAdmin(admin.ModelAdmin):
    list_display = [
        "task_name_short",
        "status_colored",
        "task_params",
        "duration",
        "enqueued_at",
        "progress_actions",
    ]
    list_filter = ["status", "queue_name",
                   "task_path", "enqueued_at", "finished_at"]
    search_fields = ["task_path", "worker_id", "error_message", "id"]
    readonly_fields = [
        "log_file_display",
        "id",
        "task_path",
        "status",
        "enqueued_at",
        "finished_at",
        "last_attempted_at",
        "worker_id",
        "duration_display",
        "queue_name",
        "error_message",
        "traceback",
    ]
    ordering = ["-enqueued_at"]
    list_per_page = 50
    date_hierarchy = "enqueued_at"

    fields = [
        "log_file_display",
        "id",
        "task_path",
        "status",
        "duration_display",
        "enqueued_at",
        "finished_at",
        "queue_name",
        "worker_id",
        "error_message",
        "traceback",
    ]

    def get_urls(self):
        custom_urls = [
            path(
                "add-task/",
                self.admin_site.admin_view(self.add_task_view),
                name="taskjob_add_task",
            ),
            path(
                "add-task/stats/",
                self.admin_site.admin_view(self.task_stats_view),
                name="taskjob_task_stats",
            ),
            path(
                "<uuid:job_id>/cancel/",
                self.admin_site.admin_view(self.cancel_job),
                name="taskjob_cancel",
            ),
            path(
                "<uuid:job_id>/logs/",
                self.admin_site.admin_view(self.get_logs_ajax),
                name="taskjob_logs",
            ),
        ]
        return custom_urls + super().get_urls()

    @admin.display(description="Task")
    def task_name_short(self, obj):
        if not obj.task_path:
            return format_html("<strong>{}</strong>", "Unknown")
        name = obj.task_path.split(".")[-1].replace("_task", "")
        return format_html("<strong>{}</strong>", name)

    @admin.display(description="Status")
    def status_colored(self, obj):
        colors = {
            TaskJobStatus.READY: "#0079bf",
            TaskJobStatus.RUNNING: "#de7e00",
            TaskJobStatus.SUCCESSFUL: "#00a04a",
            TaskJobStatus.FAILED: "#ba2121",
        }
        return format_html(
            '<span style="color: {}; font-weight: 500;">{}</span>',
            colors.get(obj.status, "#666"),
            obj.get_status_display(),
        )

    @admin.display(description="Parameters")
    def task_params(self, obj):
        kwargs = obj.kwargs or {}
        task_path = obj.task_path or ""
        params = []

        if "user_discovery_task" in task_path:
            search_query = kwargs.get("search_query")
            if search_query:
                display_query = f"{search_query[:47]}..." if len(
                    search_query) > 50 else search_query
                params.append(f"Query: {display_query}")
            if kwargs.get("set_user_status"):
                params.append(f"Status: {kwargs['set_user_status']}")

        return format_html_join(", ", "{}", ((param,) for param in params)) if params else "-"

    def _format_duration(self, total_seconds):
        if total_seconds < 60:
            return f"{total_seconds:.1f}s"

        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60

        if minutes < 60:
            return f"{minutes}m {seconds:.1f}s"

        hours = minutes // 60
        minutes %= 60

        if hours < 24:
            return f"{hours}h {minutes}m {seconds:.0f}s"

        days = hours // 24
        hours %= 24
        return f"{days}d {hours}h {minutes}m"

    @admin.display(description="Duration")
    def duration(self, obj):
        if obj.started_at and obj.finished_at:
            return self._format_duration((obj.finished_at - obj.started_at).total_seconds())
        if obj.started_at:
            running = timezone.now() - obj.started_at
            return f"{self._format_duration(running.total_seconds())} (running)"
        return "-"

    @admin.display(description="Duration")
    def duration_display(self, obj):
        return self.duration(obj)

    @admin.display(description="Actions")
    def progress_actions(self, obj):
        if obj.status not in [TaskJobStatus.READY, TaskJobStatus.RUNNING]:
            return "-"

        cancel_url = f"/admin/task_queue/taskjob/{obj.id}/cancel/"
        return format_html(
            '<div style="white-space: nowrap;">'
            '<a href="{}" class="button" '
            'style="font-size: 12px; padding: 6px 12px; background-color: #dc3545; color: white; '
            'font-weight: bold; border: none; border-radius: 4px; text-decoration: none;">'
            "🛑 STOP"
            "</a>"
            "</div>",
            cancel_url,
        )

    def _possible_log_paths(self, obj):
        log_dir = os.path.join(settings.BASE_DIR, "apps", "task_queue", "logs")
        paths = []

        if obj.result and isinstance(obj.result, dict) and obj.result.get("log_file"):
            paths.append(obj.result["log_file"])

        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                if filename.endswith(f"_{obj.id}.log"):
                    paths.append(os.path.join(log_dir, filename))

        paths.append(os.path.join(log_dir, f"{obj.id}.log"))

        seen = set()
        unique_paths = []
        for path in paths:
            if path and path not in seen:
                seen.add(path)
                unique_paths.append(path)
        return unique_paths

    def _read_log_content(self, obj):
        for path in self._possible_log_paths(obj):
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        return f.read(), path
                except OSError:
                    continue
        return None, None

    def _format_log_lines(self, log_content):
        formatted = []
        for raw_line in log_content.split("\n"):
            if not raw_line.strip():
                continue

            line = escape(raw_line)

            if " - ERROR - " in raw_line or "✗ Error saving user" in raw_line:
                formatted.append(
                    format_html(
                        '<span style="color: #f85149; font-weight: bold;">{}</span>', line)
                )
            elif " - WARNING - " in raw_line:
                formatted.append(
                    format_html(
                        '<span style="color: #f78166; font-weight: bold;">{}</span>', line)
                )
            elif " - INFO - " in raw_line:
                formatted.append(
                    format_html(
                        '<span style="color: #58a6ff;">{}</span>', line)
                )
            elif " - DEBUG - " in raw_line:
                formatted.append(
                    format_html(
                        '<span style="color: #8b949e;">{}</span>', line)
                )
            elif "✓ Successfully saved user:" in raw_line:
                formatted.append(
                    format_html(
                        '<span style="color: #56d364; font-weight: bold;">{}</span>', line)
                )
            else:
                formatted.append(line)

        return formatted

    def _live_refresh_script(self, obj):
        if obj.status != TaskJobStatus.RUNNING:
            return ""

        return format_html(
            """
            <script>
                let logRefreshInterval;
                function refreshLogs_{0}() {{
                    fetch('/admin/task_queue/taskjob/{1}/logs/')
                        .then(response => response.json())
                        .then(data => {{
                            if (data.logs) {{
                                const logContainer = document.getElementById('log-content-{0}');
                                if (logContainer) {{
                                    const isScrolledToBottom =
                                        logContainer.scrollTop >= (logContainer.scrollHeight - logContainer.clientHeight - 50);
                                    logContainer.innerHTML = data.logs;
                                    if (isScrolledToBottom) {{
                                        logContainer.scrollTop = logContainer.scrollHeight;
                                    }}
                                }}
                            }}
                            if (data.status !== 'RUNNING') {{
                                clearInterval(logRefreshInterval);
                                setTimeout(() => window.location.reload(), 1000);
                            }}
                        }})
                        .catch(err => console.log('Log refresh error:', err));
                }}
                document.addEventListener('DOMContentLoaded', function() {{
                    logRefreshInterval = setInterval(refreshLogs_{0}, 2000);
                }});
            </script>
            """,
            obj.id.hex,
            obj.id,
        )

    @admin.display(description="Task Log & Details")
    def log_file_display(self, obj):
        log_content, log_file_path = self._read_log_content(obj)

        if not log_content:
            if obj.status == TaskJobStatus.READY:
                return mark_safe(
                    '<div style="background: #1e1e1e; padding: 15px; border-radius: 6px; border-left: 4px solid #f78166;">'
                    '<p style="color: #f78166; margin: 0; font-style: italic;">'
                    "⏳ Task waiting to start... Logs will appear once the task begins executing."
                    "</p>"
                    "</div>"
                )

            if obj.status == TaskJobStatus.RUNNING:
                return mark_safe(
                    '<div style="background: #1e1e1e; padding: 15px; border-radius: 6px; border-left: 4px solid #58a6ff;">'
                    '<p style="color: #58a6ff; margin: 0; font-style: italic;">'
                    "🚀 Task starting... Logs will appear shortly. Try refreshing in a moment."
                    "</p>"
                    "</div>"
                )

            if obj.status == TaskJobStatus.SUCCESSFUL and obj.result:
                result_text = str(obj.result)
                result_preview = result_text[:1000] + \
                    ("..." if len(result_text) > 1000 else "")
                return format_html(
                    '<div style="background: #1e1e1e; padding: 15px; border-radius: 6px; border-left: 4px solid #56d364;">'
                    '<strong style="color: #56d364;">Task Result:</strong><br>'
                    '<pre style="margin: 10px 0; white-space: pre-wrap; color: #e6edf3; background: #0d1117; padding: 10px; border-radius: 4px; font-family: monospace;">{}</pre>'
                    "</div>"
                    '<p style="color: #8b949e; font-style: italic; margin-top: 15px;">'
                    "No detailed log file found for job {}"
                    "</p>",
                    result_preview,
                    obj.id,
                )

            if obj.status == TaskJobStatus.FAILED:
                error_parts = []
                if obj.error_message:
                    error_parts.append(f"Error: {obj.error_message}")
                if obj.traceback:
                    error_parts.append(f"Traceback:\n{obj.traceback}")

                if error_parts:
                    return format_html(
                        '<div style="background: #1e1e1e; border-left: 4px solid #f85149; padding: 15px; border-radius: 6px;">'
                        '<strong style="color: #f85149;">Task Failed:</strong><br>'
                        '<pre style="margin: 10px 0; white-space: pre-wrap; font-size: 12px; color: #e6edf3; background: #0d1117; padding: 10px; border-radius: 4px; font-family: monospace;">{}</pre>'
                        "</div>",
                        "\n\n".join(error_parts),
                    )

            return format_html(
                '<div style="background: #1e1e1e; padding: 15px; border-radius: 6px; border: 1px solid #3c3c3c;">'
                '<p style="color: #8b949e; font-style: italic; margin: 0;">'
                "No log file found for job {}. Log files are created in: /apps/task_queue/logs/"
                "</p>"
                "</div>",
                obj.id,
            )

        formatted_lines = self._format_log_lines(log_content)
        visible_lines = mark_safe("\n".join(str(line)
                                  for line in formatted_lines[-100:]))
        log_lines_count = len(log_content.split("\n"))
        live_label = " (Live)" if obj.status == TaskJobStatus.RUNNING else ""
        file_name = os.path.basename(
            log_file_path) if log_file_path else "unknown"
        obj_id_hex = obj.id.hex if getattr(obj, "id", None) else "unknown"
        live_script = self._live_refresh_script(obj)

        return format_html(
            '<div style="background: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 6px; padding: 15px; margin-bottom: 20px;">'
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #3c3c3c;">'
            '<strong style="color: #ffffff; font-size: 14px;">Task Log ({} lines){}</strong>'
            '<small style="color: #888;">File: {}</small>'
            "</div>"
            '<pre id="log-content-{}" style="max-height: 500px; overflow-y: auto; font-size: 12px; line-height: 1.5; background: #0d1117; border: 1px solid #3c3c3c; border-radius: 4px; padding: 15px; margin: 0; white-space: pre-wrap; word-wrap: break-word; color: #e6edf3; font-family: \'SFMono-Regular\', Consolas, \'Liberation Mono\', Menlo, monospace;">{}</pre>'
            "</div>{}",
            log_lines_count,
            live_label,
            file_name,
            obj_id_hex,
            visible_lines,
            mark_safe(live_script),
        )

    def cancel_job(self, request, job_id):
        try:
            job = TaskJob.objects.get(id=job_id)
            if job.status in [TaskJobStatus.READY, TaskJobStatus.RUNNING]:
                job.status = TaskJobStatus.CANCELLED
                job.error_message = "Cancelled by admin"
                job.finished_at = timezone.now()
                job.save(update_fields=[
                         "status", "error_message", "finished_at"])
                messages.success(request, f"Job {job_id} cancelled")
            else:
                messages.warning(
                    request,
                    f"Job {job_id} cannot be cancelled (status: {job.status})",
                )
        except TaskJob.DoesNotExist:
            messages.error(request, "Job not found")
        except Exception as exc:
            messages.error(request, f"Failed to cancel job: {exc}")

        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "../"))

    def get_logs_ajax(self, request, job_id):
        try:
            job = TaskJob.objects.get(id=job_id)
            log_content, _ = self._read_log_content(job)

            if not log_content:
                return JsonResponse({"logs": "Log file not found", "status": job.status})

            formatted_lines = self._format_log_lines(log_content)
            return JsonResponse(
                {
                    "logs": "\n".join(str(line) for line in formatted_lines),
                    "status": job.status,
                    "line_count": len(log_content.split("\n")),
                }
            )
        except TaskJob.DoesNotExist:
            return JsonResponse({"error": "Job not found"}, status=404)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}

        try:
            obj = TaskJob.objects.get(pk=object_id)
            action_buttons = []

            if obj.status in [TaskJobStatus.READY, TaskJobStatus.RUNNING]:
                action_buttons.append(
                    {
                        "url": f"/admin/task_queue/taskjob/{obj.id}/cancel/",
                        "title": "STOP TASK",
                        "class": "stop-button",
                        "style": "background-color: #dc3545; color: white;border-radius: 4px; padding: 8px 16px;  text-decoration: none;",
                    }
                )

            extra_context["action_buttons"] = action_buttons
            extra_context["job_status"] = obj.status
        except TaskJob.DoesNotExist:
            pass

        return super().change_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        return super().get_queryset(request)

    def _processed_at_stats(self, model, extra_filters=None):
        qs = model.objects.all()
        if extra_filters:
            qs = qs.filter(**extra_filters)
        total = qs.count()
        processed = qs.filter(processed_at__isnull=False).count()
        remaining = total - processed
        pct = round((processed / total) * 100, 1) if total else 0
        return {
            "total": total,
            "processed": processed,
            "remaining": remaining,
            "pct": pct,
        }

    def task_stats_view(self, request):

        task_type = request.GET.get("task_type", "")
        stats = {}

        if "user_discovery_task" in task_type:
            stats = None

        elif "process_users_task" in task_type:
            stats = self._processed_at_stats(
                User, {"status": UserStatus.CONFIRMED}
            )
            stats["label"] = "confirmed users"

        elif "process_repositories_task" in task_type:
            stats = self._processed_at_stats(
                Repo, {"owner__status": UserStatus.CONFIRMED, "is_fork": False}
            )
            stats["label"] = "repositories (confirmed owners, non-fork)"

        elif "process_gists_task" in task_type:
            stats = self._processed_at_stats(Gist)
            stats["label"] = "gists"

        elif "process_commits_task" in task_type:
            stats = self._processed_at_stats(Commit)
            stats["label"] = "commits"

        elif "find_matches_task" in task_type:
            active = Regex.objects.filter(is_active=True).count()
            never_run = Regex.objects.filter(
                is_active=True, last_processed_at__isnull=True
            ).count()
            total_matches = Match.objects.count()
            stats = {
                "active_regexes": active,
                "never_run": never_run,
                "already_run": active - never_run,
                "total_matches": total_matches,
            }

        elif "get_raw_events_task" in task_type:
            last_event = (
                RawEvent.objects.order_by("-observed_at")
                .values_list("observed_at", flat=True)
                .first()
            )
            first_event = (
                RawEvent.objects.order_by("observed_at")
                .values_list("observed_at", flat=True)
                .first()
            )
            now = datetime.now(tz=dt_timezone.utc)
            total_events = RawEvent.objects.count()

            if last_event:
                hours_since_last = round(
                    (now - last_event).total_seconds() / 3600, 1
                )
                hours_covered = round(
                    (last_event - first_event).total_seconds() / 3600, 1
                )
                stats = {
                    "total_events": total_events,
                    "first_event": first_event.strftime("%Y-%m-%d %H:%M UTC"),
                    "last_event": last_event.strftime("%Y-%m-%d %H:%M UTC"),
                    "hours_since_last": hours_since_last,
                    "hours_covered": hours_covered,
                }
            else:
                stats = {
                    "total_events": 0,
                    "first_event": None,
                    "last_event": None,
                    "hours_since_last": None,
                    "hours_covered": 0,
                }

        elif "sync_event_commits_task" in task_type:
            raw_events_for_repo = RawEvent.objects.filter(
                repo_id=OuterRef("source_repo_id")
            )
            repos_with_events = (
                Repo.objects.filter(
                    owner__status=UserStatus.CONFIRMED,
                    is_fork=False,
                    source_repo_id__isnull=False,
                )
                .annotate(has_raw_events=Exists(raw_events_for_repo))
                .filter(has_raw_events=True)
                .count()
            )
            stats = {"repos_with_events": repos_with_events}

        return JsonResponse({"stats": stats})

    def add_task_view(self, request):
        if request.method == "POST":
            form = AddTaskForm(request.POST)
            if form.is_valid():
                try:
                    task_path = form.cleaned_data["task_type"]
                    kwargs = {}

                    if task_path == "apps.task_queue.tasks.user_discovery_task":
                        kwargs["search_query"] = form.cleaned_data["search_query"]
                        if form.cleaned_data.get("set_user_status"):
                            kwargs["set_user_status"] = form.cleaned_data["set_user_status"]

                    job = enqueue(
                        task_path,
                        priority=0,
                        **kwargs,
                    )

                    messages.success(
                        request,
                        f'Task "{task_path}" added successfully with job ID: {job.id}',
                    )
                    return HttpResponseRedirect("../")
                except Exception as exc:
                    messages.error(request, f"Failed to add task: {exc}")
            else:
                messages.error(request, "Please correct the errors below.")
        else:
            form = AddTaskForm()

        context = {
            "title": "Add New Task",
            "form": form,
            "opts": self.model._meta,
            "has_change_permission": self.has_change_permission(request),
        }
        return TemplateResponse(request, "admin/task_queue/add_task.html", context)

    def has_add_permission(self, request, obj=None):
        return False
