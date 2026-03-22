from django.db import models


class GitHubToken(models.Model):
    label = models.CharField(max_length=100, unique=True,
                             help_text="Descriptive label for this token")
    token = models.CharField(
        max_length=255, help_text="GitHub personal access token")
    is_active = models.BooleanField(
        default=True, help_text="Whether this token is currently active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_github_tokens'
        ordering = ['-is_active', 'label']

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.label} ({status})"

    def get_live_rate_limit_status(self):
        if not self.is_active or not self.token:
            return None

        try:
            # Avoid circular import
            from clients.github import GitHubAPIClient
            client = GitHubAPIClient()
            rate_data = client.get_rate_limit_info(self)

            if 'error' in rate_data:
                return None

            rate_info = rate_data.get('rate', {})
            return {
                'remaining': rate_info.get('remaining', 0),
                'limit': rate_info.get('limit', 0),
                'reset': rate_info.get('reset', 0)
            }
        except:
            return None
