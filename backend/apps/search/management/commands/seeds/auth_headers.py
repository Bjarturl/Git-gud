from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "Authorization header",
        "regex_pattern": r"\bAuthorization:\s*(?:Basic|Bearer|Token)\s+[A-Za-z0-9._~+/\-=]{15,}\b",
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "X-API-KEY header",
        "regex_pattern": r"\bX[-_]?API[-_ ]?KEY\s*[:=]\s*[A-Za-z0-9._\-]{16,}\b",
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "Okta API token",
        "regex_pattern": r"\bSSWS\s+[A-Za-z0-9_\-]{42}\b",
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "Artifactory AKC token",
        "regex_pattern": r"(?:[\s=:\"])AKC[a-zA-Z0-9]{10,}",
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "Artifactory AP token",
        "regex_pattern": r"(?:[\s=:\"])AP[\dABCDEF][a-zA-Z0-9]{8,}",
        "category": RegexCategory.AUTH_HEADERS,
    },
]
