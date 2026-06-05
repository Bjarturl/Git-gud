from apps.search.models import RegexCategory

SEEDS = [
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
        "name": "Discord user token",
        "regex_pattern": r"\b[MN][A-Za-z0-9]{23}\.[\w-]{6}\.[\w-]{27}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
    {
        "name": "Discord MFA token",
        "regex_pattern": r"\bmfa\.[\w-]{84}\b",
        "category": RegexCategory.MESSAGING_COMMUNICATION,
    },
]
