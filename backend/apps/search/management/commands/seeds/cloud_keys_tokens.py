from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "Google API key",
        "regex_pattern": r"\bAIza[0-9A-Za-z\-_]{35}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google OAuth token",
        "regex_pattern": r"\bya29\.[0-9A-Za-z\-_]+\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google OAuth client ID",
        "regex_pattern": r"\b[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google OAuth client secret assignment",
        "regex_pattern": r"""\bclient_secret\b.{0,20}\b[A-Za-z0-9\-_]{24}\b""",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google OAuth client secret (GOCSPX)",
        "regex_pattern": r"\bGOCSPX-[A-Za-z0-9_\-]{28,}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google service account type marker",
        "regex_pattern": r'"type"\s*:\s*"service_account"',
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google service account private key ID",
        "regex_pattern": r'"private_key_id"\s*:\s*"[0-9a-f]{40}"',
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Google service account email domain",
        "regex_pattern": r"\b[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Firebase server key",
        "regex_pattern": r"\bAAAA[a-zA-Z0-9_-]{7}:[a-zA-Z0-9_-]{140}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Firebase project URL",
        "regex_pattern": r"\b[a-z0-9.-]+\.firebase(?:io|app)\.com\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Facebook access token",
        "regex_pattern": r"\bEAACEdEose0cBA[0-9A-Za-z]+\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "DigitalOcean personal access token",
        "regex_pattern": r"\bdop_v1_[a-f0-9]{64}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Dropbox access token",
        "regex_pattern": r"\bda2-[a-z0-9]{26}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Datadog API key",
        "regex_pattern": r"\bdapi[a-f0-9]{32}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Amazon MWS auth token",
        "regex_pattern": r"\bamzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Signed URL signature parameter",
        "regex_pattern": r"(?:[?&](?:sig|signature|X-Amz-Signature|X-Goog-Signature)=[A-Za-z0-9%+/=]{16,})",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "HashiCorp Vault token",
        "regex_pattern": r"\bhv[sbr]\.[A-Za-z0-9]{24,}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Azure client or tenant ID",
        "regex_pattern": r"(?i)(?:azure|client.?id|tenant.?id).{0,20}[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Azure storage connection string",
        "regex_pattern": r"DefaultEndpointsProtocol=https?;AccountName=[^;]{1,64};AccountKey=[A-Za-z0-9+/=]{60,}",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Azure SAS token",
        "regex_pattern": r"[?&]sv=\d{4}-\d{2}-\d{2}[^#\s]{0,500}&sig=[A-Za-z0-9%+/]{30,}",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Mapbox public token",
        "regex_pattern": r"\bpk\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]{2,}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Mapbox secret token",
        "regex_pattern": r"\bsk\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]{2,}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Cloudinary credentials URL",
        "regex_pattern": r"\bcloudinary://[0-9]+:[A-Za-z0-9_\-]+@[a-z]+\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Paddle publishable key",
        "regex_pattern": r"\bpk\.[a-zA-Z0-9]{60}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Paddle secret key",
        "regex_pattern": r"\bsk\.[a-zA-Z0-9]{60}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Paddle token key",
        "regex_pattern": r"\btk\.[a-zA-Z0-9]{60}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
]
