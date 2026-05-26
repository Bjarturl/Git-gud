from apps.search.models import RegexCategory

SEEDS = [
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
        "name": "Stripe restricted live key",
        "regex_pattern": r"\brk_live_[0-9a-zA-Z]{24}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Stripe webhook signing secret",
        "regex_pattern": r"\bwhsec_[A-Za-z0-9]{32,}\b",
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
        "name": "Square access token",
        "regex_pattern": r"\bsq0atp-[0-9A-Za-z\-_]{22}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
    {
        "name": "Square secret",
        "regex_pattern": r"\bsq0csp-[0-9A-Za-z\-_]{43}\b",
        "category": RegexCategory.PAYMENT_FINANCIAL,
    },
]
