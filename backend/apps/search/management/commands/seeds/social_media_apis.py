from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "Instagram graph token",
        "regex_pattern": r"\bIGQV[A-Za-z0-9_-]{20,}\b",
        "category": RegexCategory.SOCIAL_MEDIA_APIS,
    },
    {
        "name": "Twitter API secret or bearer token",
        "regex_pattern": r"(?i)twitter_(?:api_secret|bearer_token).{0,20}[A-Za-z0-9]{32,}",
        "category": RegexCategory.SOCIAL_MEDIA_APIS,
    },
    {
        "name": "Instagram access token (context)",
        "regex_pattern": r"(?i)instagram_access_token.{0,20}[A-Za-z0-9]{32,}",
        "category": RegexCategory.SOCIAL_MEDIA_APIS,
    },
    {
        "name": "LinkedIn TikTok or Snapchat token",
        "regex_pattern": r"(?i)(?:linkedin|tiktok|snapchat).{0,20}[A-Za-z0-9]{16,64}",
        "category": RegexCategory.SOCIAL_MEDIA_APIS,
    },
    {
        "name": "Twitch OAuth IRC token",
        "regex_pattern": r"\boauth:[a-z0-9]{30}\b",
        "category": RegexCategory.SOCIAL_MEDIA_APIS,
    },
]
