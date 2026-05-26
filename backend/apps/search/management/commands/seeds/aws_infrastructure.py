from apps.search.models import RegexCategory

SEEDS = [
    {
        "name": "AWS access key ID",
        "regex_pattern": r"\b(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS access key ID assignment",
        "regex_pattern": r"\bAWS_ACCESS_KEY_ID\b.{0,40}\b(?:A3T[A-Z0-9]|AKIA|AGPA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS secret access key assignment",
        "regex_pattern": r"\bAWS_SECRET_ACCESS_KEY\b.{0,40}\b[A-Za-z0-9/+=]{40}\b",
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
        "name": "AWS account ID assignment",
        "regex_pattern": r"\bAWS_ACCOUNT_ID\b.{0,40}\b[0-9]{12}\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
    {
        "name": "AWS ECR registry URL",
        "regex_pattern": r"\b[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com\b",
        "category": RegexCategory.AWS_INFRASTRUCTURE,
    },
]
