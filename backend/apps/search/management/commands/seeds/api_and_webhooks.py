from apps.search.models import RegexCategory

SEEDS = [
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
        "name": "Sentry DSN",
        "regex_pattern": r"\bhttps://[a-f0-9]{32}(?::[a-f0-9]{32})?@(?:o\d+\.ingest\.)?sentry\.io/\d+\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Grafana cloud API key",
        "regex_pattern": r"\bglc_eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Notion integration token",
        "regex_pattern": r"\bsecret_[A-Za-z0-9]{43}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Airtable API key",
        "regex_pattern": r"\bkey[A-Za-z0-9]{14}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Airtable personal access token",
        "regex_pattern": r"\bpat[A-Za-z0-9]{14}\.[a-f0-9]{64}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Typeform API token",
        "regex_pattern": r"\btfp_[A-Za-z0-9_]{40,50}\b",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Shodan API key (context)",
        "regex_pattern": r"(?i)shodan.{0,30}[A-Za-z0-9]{30,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Algolia API key (context)",
        "regex_pattern": r"(?i)algolia.{0,30}[A-Za-z0-9]{30,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "New Relic API key (context)",
        "regex_pattern": r"(?i)newrelic.{0,30}[A-Za-z0-9]{40,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Salesforce token (context)",
        "regex_pattern": r"(?i)salesforce.{0,30}[A-Za-z0-9!]{15,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "HubSpot API key",
        "regex_pattern": r"(?i)hubspot.{0,30}hapikey[A-Za-z0-9\-_]{30,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "WakaTime API key (context)",
        "regex_pattern": r"(?i)wakatime.{0,30}[A-Za-z0-9]{8}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{12}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "Zendesk API token (context)",
        "regex_pattern": r"(?i)zendesk.{0,30}[A-Za-z0-9_\-]{40,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
    {
        "name": "PagerDuty API key (context)",
        "regex_pattern": r"(?i)pagerduty.{0,30}[A-Za-z0-9+]{20,}",
        "category": RegexCategory.API_AND_WEBHOOKS,
    },
]
