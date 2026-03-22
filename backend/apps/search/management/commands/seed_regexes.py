from django.core.management.base import BaseCommand

from apps.search.models import Regex, RegexCategory


REGEX_SEEDS = [
    {
        "name": "OpenAI API key",
        "regex_pattern": r"\bsk-[A-Za-z0-9]{48}\b",
        "category": RegexCategory.AI_TOKENS,
    },
    {
        "name": "OpenAI project API key",
        "regex_pattern": r"\bsk-proj-[A-Za-z0-9]{48}\b",
        "category": RegexCategory.AI_TOKENS,
    },
    {
        "name": "Legacy OpenAI-style key",
        "regex_pattern": r"\bsk-[A-Za-z0-9]{32}\b",
        "category": RegexCategory.AI_TOKENS,
    },
    {
        "name": "Anthropic API key",
        "regex_pattern": r"\bsk-ant-api03-[A-Za-z0-9_-]{95}\b",
        "category": RegexCategory.AI_TOKENS,
    },
    {
        "name": "Hugging Face token",
        "regex_pattern": r"\bhf_[A-Za-z0-9]{34}\b",
        "category": RegexCategory.AI_TOKENS,
    },
    {
        "name": "Cohere API key",
        "regex_pattern": r"\bco\.[A-Za-z0-9]{24}\b",
        "category": RegexCategory.AI_TOKENS,
    },
    {
        "name": "Replicate API token",
        "regex_pattern": r"\br8_[A-Za-z0-9]{32}\b",
        "category": RegexCategory.AI_TOKENS,
    },

    {
        "name": "Postman API key",
        "regex_pattern": r"\bPMAK-[A-Za-z0-9]{24}-[A-Za-z0-9]{34}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Discord webhook URL",
        "regex_pattern": r"\bhttps://discord(?:app)?\.com/api/webhooks/[0-9]{17,19}/[A-Za-z0-9_-]{68}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Zapier webhook URL",
        "regex_pattern": r"\bhttps://hooks\.zapier\.com/hooks/catch/[0-9]+/[a-z0-9]+\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Generic API key assignment",
        "regex_pattern": r"""(?ix)
\b(?:api[_ -]?key|apikey)\b
\s*[:=]\s*
["']?
(?=[A-Za-z0-9._\-/+=]{16,128}\b)
(?=[A-Za-z0-9._\-/+=]*[A-Za-z])
(?=[A-Za-z0-9._\-/+=]*\d)
([A-Za-z0-9._\-/+=]{16,128})
["']?
""",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Bearer token",
        "regex_pattern": r"\bBearer\s+[A-Za-z0-9\-._~+/=]{20,}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Mailgun API key",
        "regex_pattern": r"\bkey-[0-9a-zA-Z]{32}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Mailchimp API key",
        "regex_pattern": r"\b[0-9a-f]{32}-us[0-9]{1,2}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },

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
        "name": "AWS secret access key assignment",
        "regex_pattern": r"\bAWS_SECRET_ACCESS_KEY\b.{0,40}\b[A-Za-z0-9/+=]{40}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS access key ID assignment",
        "regex_pattern": r"\bAWS_ACCESS_KEY_ID\b.{0,40}\b(?:A3T[A-Z0-9]|AKIA|AGPA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS session token assignment",
        "regex_pattern": r"\bAWS_SESSION_TOKEN\b.{0,80}[A-Za-z0-9/+=]{80,}",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS STS token fragment",
        "regex_pattern": r"\bIQoJb3JpZ2luX2Vj[A-Za-z0-9/+=]{20,}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS access key ID",
        "regex_pattern": r"\b(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS account ID assignment",
        "regex_pattern": r"\bAWS_ACCOUNT_ID\b.{0,40}\b[0-9]{12}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS ECR registry URL",
        "regex_pattern": r"\b[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },

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
        "name": "Signed URL signature parameter",
        "regex_pattern": r"(?:[?&](?:sig|signature|X-Amz-Signature|X-Goog-Signature)=[A-Za-z0-9%+/=]{16,})",
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
        "name": "Amazon MWS auth token",
        "regex_pattern": r"\bamzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },
    {
        "name": "Facebook access token",
        "regex_pattern": r"\bEAACEdEose0cBA[0-9A-Za-z]+\b",
        "category": RegexCategory.CLOUD_KEYS_TOKENS,
    },

    {
        "name": "Database connection URL",
        "regex_pattern": r"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|mariadb|oracle|sqlserver|mssql|redis|rediss|amqp|amqps)://[^/\s:@]+:[^/\s@]+@[^/\s]+\b",
        "category": RegexCategory.CONNECTION_STRINGS_DB,
    },
    {
        "name": "DATABASE_URL assignment",
        "regex_pattern": r"\bDATABASE_URL\b.{0,5}(?:postgres(?:ql)?|mysql|mariadb|redis|rediss|mssql|sqlserver|mongodb(?:\+srv)?|amqp|amqps)://[^\s/]+:[^\s/]+@[^\s/]+",
        "category": RegexCategory.CONNECTION_STRINGS_DB,
    },
    {
        "name": "MONGODB_URI assignment",
        "regex_pattern": r"\bMONGODB_URI\b.{0,5}mongodb(?:\+srv)?:\/\/[^\s]+",
        "category": RegexCategory.CONNECTION_STRINGS_DB,
    },
    {
        "name": "JDBC connection string",
        "regex_pattern": r"\bjdbc:(?:mysql|postgresql|sqlserver|oracle):[^ \n\r\t;\"]+",
        "category": RegexCategory.CONNECTION_STRINGS_DB,
    },

    {
        "name": "GitHub token",
        "regex_pattern": r"\bgh[pousr]_[A-Za-z0-9_]{36,82}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "GitHub fine-grained PAT",
        "regex_pattern": r"\bgithub_pat_[A-Za-z0-9_]{82}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "GitLab PAT",
        "regex_pattern": r"\bglpat-[A-Za-z0-9\-_]{20}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "PyPI token",
        "regex_pattern": r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9-_]{50,1000}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "RubyGems token",
        "regex_pattern": r"\brubygems_[a-zA-Z0-9]{48}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "NPM token",
        "regex_pattern": r"\bnpm_[A-Za-z0-9]{36}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Docker PAT",
        "regex_pattern": r"\bdckr_pat_[a-zA-Z0-9_-]{36}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },

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
        "name": "Azure App Service URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.azurewebsites\.net(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "Vercel deployment URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.vercel\.app(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "Netlify deployment URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.netlify\.app(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "Heroku app URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.herokuapp\.com(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "CloudFront URL",
        "regex_pattern": r"\bhttps://[a-z0-9]+\.cloudfront\.net(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "Cloud Functions URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.cloudfunctions\.net(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "App Engine URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.appspot\.com(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "DigitalOcean app URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.ondigitalocean\.app(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "Railway app URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.railway\.app(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },
    {
        "name": "Render app URL",
        "regex_pattern": r"\bhttps://[a-z0-9-]+\.onrender\.com(?:/[^\s]*)?\b",
        "category": RegexCategory.HOSTING_PLATFORMS,
    },

    {
        "name": "JWT token",
        "regex_pattern": r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*\b",
        "category": RegexCategory.JWT_TOKENS,
    },

    {
        "name": "Slack token",
        "regex_pattern": r"\bxox[pbra]-[0-9A-Za-z\-]{23,72}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
    {
        "name": "Slack webhook URL",
        "regex_pattern": r"\bhttps://hooks\.slack\.com/(?:services|workflows)/[A-Z0-9/_-]{30,}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
    {
        "name": "Twilio SID or key",
        "regex_pattern": r"\b(?:AC|SK|AP)[a-f0-9]{32}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
    {
        "name": "SendGrid API key",
        "regex_pattern": r"\bSG\.[\w\-_]{20,24}\.[\w\-_]{39,50}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
    {
        "name": "Telegram bot token",
        "regex_pattern": r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
    {
        "name": "Microsoft Teams webhook URL",
        "regex_pattern": r"\bhttps://[a-z0-9]+\.webhook\.office\.com/webhookb2/[a-f0-9\-]+@[a-f0-9\-]+/IncomingWebhook/[a-f0-9]+/[a-f0-9\-]+\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },

    {
        "name": "IPv4 address",
        "regex_pattern": r"\b(?!(?:0|10|127|192)\.)(?!169\.254\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\b",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },
    {
        "name": "IPv4 CIDR",
        "regex_pattern": r"\b(?!(?:0|10|127|192)\.)(?!169\.254\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])/(?:3[0-2]|[12]?[0-9])\b",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },
    {
        "name": "Full IPv6 address",
        "regex_pattern": r"\b(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}\b",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },
    {
        "name": "IPv6 CIDR",
        "regex_pattern": r"\b(?:[0-9A-Fa-f:]+:+[0-9A-Fa-f:]*)/(?:12[0-8]|1[01][0-9]|[1-9]?[0-9])\b",
        "category": RegexCategory.NETWORK_INFRASTRUCTURE,
    },

    {
        "name": "Credential assignment",
        "regex_pattern": r"""(?ix)
\b(pass(?:wd|word)?|pwd|secret|api[_-]?key|apikey|token|auth(?:[_-]?token)?|access[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key|signature|sig)\b[\w\-]*
\s*(?:=|:|=>)\s*
["']?
(?!true\b|false\b|null\b|none\b|nil\b|undefined\b|nan\b|changeme\b|change[_-]?me\b|example\b|sample\b|dummy\b|test\b|testing\b|redacted\b|xxxxx+\b)
(?=[^\s"'&;\n\r]{8,128}\b)
(?=[^\s"'&;\n\r]*[A-Za-z])
(?=[^\s"'&;\n\r]*\d|[^\s"'&;\n\r]*[_\-/+=])
([^\s"'&;\n\r]{8,128})
["']?
""",
        "category": RegexCategory.PASSWORDS_AND_SECRETS_GENERIC,
    },
    {
        "name": "Exported credential variable",
        "regex_pattern": r"""(?ix)
\bexport\s+
(pass(?:wd|word)?|pwd|secret|api[_-]?key|apikey|token|client[_-]?secret)\b[\w\-]*
\s*=\s*
["']?
(?!true\b|false\b|null\b|none\b|nil\b|undefined\b|nan\b|changeme\b|change[_-]?me\b|example\b|sample\b|dummy\b|test\b|testing\b|redacted\b|xxxxx+\b)
(?=[^\s"'\\]{8,128}\b)
(?=[^\s"'\\]*[A-Za-z])
(?=[^\s"'\\]*\d|[^\s"'\\]*[_\-/+=])
([^\s"'\\]{8,128})
["']?
""",
        "category": RegexCategory.PASSWORDS_AND_SECRETS_GENERIC,
    },
    {
        "name": "Quoted JSON or YAML credential",
        "regex_pattern": r"""(?ix)
["'](?:pass(?:wd|word)?|pwd|secret|api[_-]?key|apikey|token|client[_-]?secret|private[_-]?key)["']
\s*:\s*
["']
(?!true\b|false\b|null\b|none\b|nil\b|undefined\b|nan\b|changeme\b|change[_-]?me\b|example\b|sample\b|dummy\b|test\b|testing\b|redacted\b|xxxxx+\b)
(?=[^"'\n\r]{8,128}\b)
(?=[^"'\n\r]*[A-Za-z])
(?=[^"'\n\r]*\d|[^"'\n\r]*[_\-/+=])
([^"'\n\r]{8,128})
["']
""",
        "category": RegexCategory.PASSWORDS_AND_SECRETS_GENERIC,
    },
    {
        "name": "Credential in URL parameter",
        "regex_pattern": r"""(?ix)
[?&](pass(?:wd|word)?|pwd|db_password|root_password|secret|api[_-]?key|apikey|token|access[_-]?token|refresh[_-]?token)[\w\-]*=
(?!true\b|false\b|null\b|none\b|nil\b|undefined\b|nan\b|changeme\b|change[_-]?me\b|example\b|sample\b|dummy\b|test\b|testing\b|redacted\b|xxxxx+\b)
(?=[^&#\s"';\n\r]{8,128}\b)
(?=[^&#\s"';\n\r]*[A-Za-z])
(?=[^&#\s"';\n\r]*\d|[^&#\s"';\n\r]*[_\-/+=])
([^&#\s"';\n\r]{8,128})
""",
        "category": RegexCategory.PASSWORDS_AND_SECRETS_GENERIC,
    },

    {
        "name": "Stripe publishable live key",
        "regex_pattern": r"\bpk_live_[0-9a-zA-Z]{24,}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Stripe secret live key",
        "regex_pattern": r"\bsk_live_[0-9a-zA-Z]{24,}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Braintree production access token",
        "regex_pattern": r"\baccess_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Razorpay key",
        "regex_pattern": r"\brzp_\w{2,6}_\w{10,20}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Shopify token",
        "regex_pattern": r"\bshp(?:at|ca|pa|ss)_[a-fA-F0-9]{32}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Square token",
        "regex_pattern": r"\bsq0[a-z]{3}-[0-9A-Za-z\-_]{22,43}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Stripe restricted live key",
        "regex_pattern": r"\brk_live_[0-9a-zA-Z]{24}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Square access token",
        "regex_pattern": r"\bsq0atp-[0-9A-Za-z\-_]{22}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Square secret",
        "regex_pattern": r"\bsq0csp-[0-9A-Za-z\-_]{43}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },

    {
        "name": "Icelandic kennitala",
        "regex_pattern": r"\b(?:[0-2][0-9]|3[01])(?:0[1-9]|1[0-2])[0-9]{2}[-\s]?[0-9]{2}[2-9][089]\b",
        "category": RegexCategory.PII_ICELANDIC,
    },
    {
        "name": "Icelandic patronymic surname",
        "regex_pattern": r"\b[A-ZÁÐÉÍÓÚÝÞÆÖ][a-zà-öu-ÿ]+(?:sson|dóttir|dottir)\b",
        "category": RegexCategory.PII_ICELANDIC,
    },
    {
        "name": "Email address",
        "regex_pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "category": RegexCategory.PII_ICELANDIC,
    },

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
        "name": "Instagram graph token",
        "regex_pattern": r"\bIGQV[A-Za-z0-9_-]{20,}\b",
        "category": RegexCategory.SOCIAL_MEDIA_APIS,
    },
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
        "name": "Username assignment",
        "regex_pattern": r"""(?i)\b(?:user(?:name)?|login|admin_user|db_user)\s*[:=>]{1,2}\s*["']([^"'\s]{3,})["']""",
        "category": RegexCategory.USERNAMES,
    },
]


class Command(BaseCommand):
    help = "Seed the regex catalog used by the search app"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing regex rows matched by seed name and reset progress when pattern changes",
        )

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        reset_progress_count = 0

        for item in REGEX_SEEDS:
            defaults = {
                "name": item["name"],
                "regex_pattern": item["regex_pattern"],
                "category": item["category"],
            }

            obj = Regex.objects.filter(name=item["name"]).first()

            if obj is None:
                obj, created = Regex.objects.get_or_create(
                    regex_pattern=item["regex_pattern"],
                    defaults=defaults,
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Created: {obj.name}"))
                    continue

                if not obj.name and obj.regex_pattern == item["regex_pattern"]:
                    obj.name = item["name"]
                    obj.category = item["category"]
                    obj.save(update_fields=["name", "category", "updated_at"])
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"Updated: {obj.name}"))
                    continue

            if not options["update"]:
                continue

            changed_fields = []
            reset_progress = False

            if obj.regex_pattern != item["regex_pattern"]:
                obj.regex_pattern = item["regex_pattern"]
                obj.last_processed_at = None
                changed_fields.extend(["regex_pattern", "last_processed_at"])
                reset_progress = True

            if obj.name != item["name"]:
                obj.name = item["name"]
                changed_fields.append("name")

            if obj.category != item["category"]:
                obj.category = item["category"]
                changed_fields.append("category")

            if changed_fields:
                changed_fields.append("updated_at")
                obj.save(update_fields=changed_fields)
                updated_count += 1
                if reset_progress:
                    reset_progress_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Updated and reset progress: {obj.name}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Updated: {obj.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} regexes, updated {updated_count} regexes, reset progress for {reset_progress_count} regexes."
            )
        )
