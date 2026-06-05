from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "Private key block",
        "regex_pattern": r"-----BEGIN (?:RSA|OPENSSH|GPG|DSA|EC|PGP)? ?PRIVATE KEY(?: BLOCK)?-----",
        "category": RegexCategory.PRIVATE_KEYS,
    },
    {
        "name": "PuTTY private key header",
        "regex_pattern": r"\bPuTTY-User-Key-File-2:\s*ssh-(?:rsa|ed25519|ecdsa)\b",
        "category": RegexCategory.PRIVATE_KEYS,
    },
    {
        "name": "Age secret key",
        "regex_pattern": r"\bAGE-SECRET-KEY-1[0-9A-Z]{58}\b",
        "category": RegexCategory.PRIVATE_KEYS,
    },
    {
        "name": "Kubernetes client key data",
        "regex_pattern": r"\bclient-key-data:\s+[A-Za-z0-9+/=]{100,}",
        "category": RegexCategory.PRIVATE_KEYS,
    },
    {
        "name": "Kubernetes certificate authority data",
        "regex_pattern": r"\bcertificate-authority-data:\s+[A-Za-z0-9+/=]{100,}",
        "category": RegexCategory.PRIVATE_KEYS,
    },
]
