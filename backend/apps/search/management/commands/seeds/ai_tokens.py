from apps.search.models import RegexCategory

SEEDS = [
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
]
