from django import forms


class AddTaskForm(forms.Form):
    TASK_CHOICES = [
        ("apps.task_queue.tasks.user_discovery_task", "GitHub User Discovery"),
        ("apps.task_queue.tasks.process_users_task", "Process Users"),
        ("apps.task_queue.tasks.process_repositories_task", "Process Repositories"),
        ("apps.task_queue.tasks.process_gists_task", "Process Gists"),
        ("apps.task_queue.tasks.process_commits_task", "Process Commits"),
        ("apps.task_queue.tasks.find_matches_task", "Find Matches"),
        ("apps.task_queue.tasks.get_raw_events_task", "Get Raw Events"),
        ("apps.task_queue.tasks.sync_event_commits_task", "Sync Event Commits"),

    ]

    task_type = forms.ChoiceField(
        choices=TASK_CHOICES,
        initial="apps.task_queue.tasks.user_discovery_task",
        label="Task Type",
    )

    search_query = forms.CharField(
        max_length=500,
        required=False,
        label="Search Query",
    )

    set_user_status = forms.ChoiceField(
        choices=[
            ("", "Keep current status"),
            ("Confirmed", "Confirmed"),
            ("Unknown", "Unknown"),
            ("Hidden", "Hidden"),
        ],
        required=False,
        label="Set User Status",
    )

    def clean(self):
        cleaned_data = super().clean()
        task_type = cleaned_data.get("task_type")

        if task_type == "apps.task_queue.tasks.user_discovery_task":
            if not cleaned_data.get("search_query"):
                self.add_error("search_query", "Search query is required.")

        return cleaned_data
