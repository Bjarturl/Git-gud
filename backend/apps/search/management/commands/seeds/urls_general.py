from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "HTTP or HTTPS IPv4 URL",
        "regex_pattern": r"\bhttps?://(?!(?:0|10|127|192)\.)(?!169\.254\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::[0-9]{1,5})?(?:/[^\s]*)?\b",
        "category": RegexCategory.URLS_GENERAL,
    },
    {
        "name": "FTP SFTP or SSH URL with credentials",
        "regex_pattern": r"\b(?:ftp|sftp|ssh)://[^/\s:@]+:[^/\s@]+@[^/\s]+\b",
        "category": RegexCategory.URLS_GENERAL,
    },
    {
        "name": "HTTPS URL with embedded credentials",
        "regex_pattern": r"\bhttps?://[A-Za-z0-9._%+\-]{1,64}:[A-Za-z0-9._%+\-!@#$^&*]{6,128}@[A-Za-z0-9][A-Za-z0-9\-]*\.[A-Za-z]{2,}\b",
        "category": RegexCategory.URLS_GENERAL,
    },
]
