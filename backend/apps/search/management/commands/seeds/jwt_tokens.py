from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "JWT token",
        "regex_pattern": r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*\b",
        "category": RegexCategory.JWT_TOKENS,
    },
]
