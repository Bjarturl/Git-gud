from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "Authorization header",
        "regex_pattern": (
            r"\bAuthorization:\s*"
            r"(?:Basic|Bearer|Token|Digest|NTLM|AWS4-HMAC-SHA256|MAC|ApiKey|Negotiate)"
            r"\s+[A-Za-z0-9._~+/\-=]{15,}"
        ),
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "Proxy-Authorization header",
        "regex_pattern": (
            r"\bProxy-Authorization:\s*"
            r"(?:Basic|Bearer|Token|Digest|NTLM)"
            r"\s+[A-Za-z0-9._~+/\-=]{15,}"
        ),
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "X-API-KEY header",
        "regex_pattern": r"\bX[-_]?API[-_ ]?KEY\s*[:=]\s*[A-Za-z0-9._\-]{16,}\b",
        "category": RegexCategory.AUTH_HEADERS,
    },
    {
        "name": "X-Auth / X-Access token header",
        "regex_pattern": (
            r"(?i)\bX[-_]"
            r"(?:Auth[-_](?:Token|Key|Secret)|Access[-_]Token"
            r"|Functions[-_]Key|RapidAPI[-_]Key|Goog[-_]Api[-_]Key)"
            r"\s*[:=]\s*[A-Za-z0-9._~+/\-=]{16,}"
        ),
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
]
