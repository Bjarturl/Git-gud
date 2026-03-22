from django.apps import AppConfig


class TaskQueueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.task_queue'
