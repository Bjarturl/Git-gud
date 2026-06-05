from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "Docker auth assignment",
        "regex_pattern": r"\bDOCKER_(?:PASSWORD|AUTH|TOKEN|LOGIN)\b.{0,50}[A-Za-z0-9+/=]{16,}",
        "category": RegexCategory.DOCKER_CONTAINER_REGISTRY,
    },
    {
        "name": "Docker config auth value",
        "regex_pattern": r'"auth"\s*:\s*"[A-Za-z0-9+/=]{20,}"',
        "category": RegexCategory.DOCKER_CONTAINER_REGISTRY,
    },
    {
        "name": "Container registry URL",
        "regex_pattern": r"\b(?:gcr\.io|azurecr\.io|registry\.gitlab\.com)/[a-z0-9][a-z0-9._/-]+\b",
        "category": RegexCategory.DOCKER_CONTAINER_REGISTRY,
    },
]
