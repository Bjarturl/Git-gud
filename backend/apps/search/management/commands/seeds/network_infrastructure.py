from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "IPv4 address",
        "regex_pattern": r"\b(?!(?:0|10|127|192)\.)(?!169\.254\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9])\b",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },
    {
        "name": "IPv4 CIDR",
        "regex_pattern": r"\b(?!(?:0|10|127|192)\.)(?!169\.254\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])/(?:3[0-2]|[12]?[0-9])\b",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },
    {
        "name": "Windows local file path",
        "regex_pattern": r"[A-Za-z]:\\{1,2}[^\\\n\r\"'<>|?*/]{2,}(?:\\{1,2}[^\\\n\r\"'<>|?*/]{2,})+",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },
]
