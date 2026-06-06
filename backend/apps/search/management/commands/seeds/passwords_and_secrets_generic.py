from apps.search.models import RegexCategory

CAT = RegexCategory.PASSWORDS_AND_SECRETS_GENERIC

# Shared fragments
_EXCL = r"(?!(?:true|false|null|none|nil|undefined|changeme|example|sample|dummy|test(?:ing)?|redacted|x{4,})\b)"
_KW   = r"(?:pass(?:wd|word|phrase|key)?|secret|token|api[_-]?key|auth|private[_-]?key|jwt|oauth)"


def _assign(keyword: str) -> str:
    """
    Matches any assignment of a credential keyword, with optional prefix/suffix and
    optional quoting of both key and value.  Covers env file, code, YAML, and JSON.
    - (?:[a-z0-9_]+_)* — any prefix (USER_, GOOGLE_CLIENT_, …)
    - (?<![a-zA-Z'"]) — keyword not mid-word (blocks bypass, compass, …)
    - ['"]?KEYWORD['"]? — optional quotes around the key (JSON "password": …)
    - (?:_[a-z0-9_]+)* — any suffix (_KEY, _FROM, …)
    """
    return (
        r"(?i)(?:[a-z0-9_]+_)*(?<![a-zA-Z'\"])['\"]?"
        + keyword
        + r"(?:_[a-z0-9_]+)*['\"]?\s*(?:=>|[=:])\s*['\"]?"
        + _EXCL
        + r"([^'\"\s\n\r#]{6,256})"
    )


SEEDS = [
    # --- simple per-keyword assignment patterns ---
    # Each covers env file (USER_PASS=x), code (password = x), YAML (key: x),
    # JSON ("key": "x"), and shell export (export PASSWORD=x).

    {"name": "Password assignment",              "regex_pattern": _assign(r"pass(?:w(?:or)?d|wd|phrase|key)?"), "category": CAT},
    {"name": "Secret assignment",                "regex_pattern": _assign(r"secret"),                           "category": CAT},
    {"name": "Token assignment",                 "regex_pattern": _assign(r"token"),                            "category": CAT},
    {"name": "API key assignment",               "regex_pattern": _assign(r"api_?key"),                         "category": CAT},
    {"name": "Auth credential assignment",       "regex_pattern": _assign(r"auth"),                             "category": CAT},
    {"name": "Private key assignment",           "regex_pattern": _assign(r"private_?key"),                     "category": CAT},
    {"name": "JWT assignment",                   "regex_pattern": _assign(r"jwt"),                              "category": CAT},
    {"name": "OAuth assignment",                 "regex_pattern": _assign(r"oauth"),                            "category": CAT},
    {"name": "Encryption or master key assignment", "regex_pattern": _assign(r"(?:encryption|master)_?key"),   "category": CAT},

    # --- special-syntax patterns ---
    # Cover forms the assignment patterns cannot: || / ?? fallback, function default
    # args, shell ${KEY:-default}, and URL query parameters.

    {
        "name": "Credential JS or null-coalescing fallback",
        "regex_pattern": (
            r"(?i)\b" + _KW + r"\b[\w\-]*\s*(?:\|\|=?|\?\?=?|\.get\([^,)]+,\s*)\s*['\"]"
            + _EXCL + r"([^'\"\s\n\r]{4,128})['\"]"
        ),
        "category": CAT,
    },
    {
        "name": "Credential env-or-fallback assignment",
        "regex_pattern": (
            r"(?i)\b" + _KW + r"\b[\w\-]*\s*=\s*[^\n\r]{0,200}?(?:\|\||\?\?)\s*['\"]"
            + _EXCL + r"([^'\"\s\n\r]{4,128})['\"]"
        ),
        "category": CAT,
    },
    {
        "name": "Credential function default argument",
        "regex_pattern": (
            r"(?i)(?:[a-z0-9_]+_)*(?<![a-zA-Z'\"])['\"]?"
            + _KW
            + r"(?:_[a-z0-9_]+)*['\"]?\s*(?:=>|[=:])\s*[^\n\r]{0,40}?"
            + r"(?:getenv|environ\.get|env\.fetch|env\.get|getProperty|get_env|get_secret"
            r"|config\.get|cfg\.get|settings\.get|getConfig|get_config)"
            + r"\s*\([^,)\n\r]{0,80},\s*['\"]"
            + _EXCL + r"([^'\"\s\n\r]{4,128})['\"]"
        ),
        "category": CAT,
    },
    {
        "name": "Shell credential parameter expansion",
        "regex_pattern": r"(?i)\$\{" + _KW + r"[\w]*:-" + _EXCL + r"([^'\"\s\n\r}{]{4,128})\}",
        "category": CAT,
    },
    {
        "name": "Credential in URL parameter",
        "regex_pattern": (
            r"(?i)[?&](?:pass(?:wd|word)?|secret|token|api[_-]?key|auth)[\w\-]*="
            + _EXCL + r"(?=[^&#\s\n\r]{6,128})(?=[^&#\s\n\r]*[A-Za-z])(?=[^&#\s\n\r]*\d)([^&#\s\n\r]{6,128})"
        ),
        "category": CAT,
    },
    {
        "name": "Ansible Vault encrypted content",
        "regex_pattern": r"\$ANSIBLE_VAULT;[0-9]+\.[0-9]+;AES256",
        "category": CAT,
    },
]
