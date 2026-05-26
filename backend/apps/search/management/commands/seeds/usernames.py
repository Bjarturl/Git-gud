from apps.search.models import RegexCategory

_EXCL = r"(?!(?:true|false|null|none|nil|undefined|changeme|example|sample|dummy|test(?:ing)?|redacted|x{4,})\b)"

SEEDS = [
    {
        "name": "Username assignment (quoted)",
        "regex_pattern": r"""(?i)\b(?:user(?:name)?|login|admin_user|db_user)\s*[:=>]{1,2}\s*["']([^"'\s]{3,})["']""",
        "category": RegexCategory.USERNAMES,
    },
    {
        "name": "Username assignment (unquoted)",
        "regex_pattern": (
            r"""(?i)(?<![a-zA-Z'"])\b(?:user(?:name)?|login)\s*[=:]\s*"""
            + _EXCL
            + r"""([^\s\n\r#'"]{3,256})"""
        ),
        "category": RegexCategory.USERNAMES,
    },
]
