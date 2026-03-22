from django.db import models
from django.db.models import Q
from django.utils import timezone


class RegexCategory(models.TextChoices):
    AI_TOKENS = "Ai tokens", "Ai tokens"
    API_AND_WEBHOOKS = "Api and webhooks", "Api and webhooks"
    AUTH_HEADERS = "Auth headers", "Auth headers"
    AWS_INFRASTRUCTURE = "Aws infrastructure", "Aws infrastructure"
    CLOUD_KEYS_TOKENS = "Cloud keys tokens", "Cloud keys tokens"
    CONNECTION_STRINGS_DB = "Connection strings db", "Connection strings db"
    DEVELOPMENT_TOOLS = "Development tools", "Development tools"
    DOCKER_CONTAINER_REGISTRY = "Docker container registry", "Docker container registry"
    HOSTING_PLATFORMS = "Hosting platforms", "Hosting platforms"
    JWT_TOKENS = "Jwt tokens", "Jwt tokens"
    MESSAGING_COMMUNICATION = "Messaging communication", "Messaging communication"
    NETWORK_INFRASTRUCTURE = "Network infrastructure", "Network infrastructure"
    PASSWORDS_AND_SECRETS_GENERIC = "Passwords and secrets generic", "Passwords and secrets generic"
    PAYMENT_FINANCIAL = "Payment financial", "Payment financial"
    PII_ICELANDIC = "Pii icelandic", "Pii icelandic"
    PRIVATE_KEYS = "Private keys", "Private keys"
    SOCIAL_MEDIA_APIS = "Social media apis", "Social media apis"
    URLS_GENERAL = "Urls general", "Urls general"
    USEREMAIL_PASS_COMBOS = "User email pass combos", "User email pass combos"
    USERNAMES = "Usernames", "Usernames"
    UUIDS = "Uuids", "Uuids"
    OTHER = "Other", "Other"


class MatchType(models.TextChoices):
    ADDITION = "Addition", "Addition"
    DELETION = "Deletion", "Deletion"


class Regex(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    regex_pattern = models.TextField()
    is_active = models.BooleanField(default=True)

    category = models.CharField(
        max_length=50,
        choices=RegexCategory.choices,
        default=RegexCategory.OTHER,
    )

    last_processed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "search_regex"
        verbose_name_plural = "Regexes"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_active", "last_processed_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            current = (
                Regex.objects
                .filter(pk=self.pk)
                .values("name", "regex_pattern", "category", "is_active")
                .first()
            )
            if current and (
                current["name"] != self.name
                or current["regex_pattern"] != self.regex_pattern
                or current["category"] != self.category
                or current["is_active"] != self.is_active
            ):
                self.last_processed_at = None

                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add("last_processed_at")
                    kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.get_category_display()}) {self.name or self.regex_pattern}"


class Match(models.Model):
    regex = models.ForeignKey(
        Regex,
        on_delete=models.CASCADE,
        related_name="matches",
    )

    commit = models.ForeignKey(
        "git_data.Commit",
        on_delete=models.CASCADE,
        related_name="matches",
        null=True,
        blank=True,
    )

    gist = models.ForeignKey(
        "git_data.Gist",
        on_delete=models.CASCADE,
        related_name="matches",
        null=True,
        blank=True,
    )

    match_type = models.CharField(
        max_length=10,
        choices=MatchType.choices,
    )

    match = models.TextField()
    raw_match = models.TextField()
    filename = models.CharField(max_length=1024, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "search_match"
        verbose_name_plural = "Matches"
        indexes = [
            models.Index(fields=["regex"]),
            models.Index(fields=["commit"]),
            models.Index(fields=["gist"]),
            models.Index(fields=["match_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(commit__isnull=False) | Q(gist__isnull=False),
                name="match_has_commit_or_gist",
            ),
            models.CheckConstraint(
                condition=~(Q(commit__isnull=False) & Q(gist__isnull=False)),
                name="match_not_both_commit_and_gist",
            ),
            models.UniqueConstraint(
                fields=["regex", "commit", "match_type", "match", "filename"],
                condition=Q(commit__isnull=False),
                name="uniq_commit_match",
            ),
            models.UniqueConstraint(
                fields=["regex", "gist", "match_type", "match", "filename"],
                condition=Q(gist__isnull=False),
                name="uniq_gist_match",
            ),
        ]

    def __str__(self):
        return f"{self.match[:50]}{'...' if len(self.match) > 50 else ''}"
