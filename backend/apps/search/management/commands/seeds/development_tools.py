from apps.search.models import RegexCategory

SEEDS = [
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
        "name": "GitLab private token (context)",
        "regex_pattern": r"(?i)gitlab_(?:private_token|token).{0,20}[A-Za-z0-9]{20,}",
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
        "name": "Heroku API key (context)",
        "regex_pattern": r"(?i)heroku_api_key.{0,20}[A-Za-z0-9]{32,}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Travis CI token",
        "regex_pattern": r"(?i)travis.{0,30}[A-Za-z0-9]{20,}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "CircleCI token",
        "regex_pattern": r"(?i)circleci.{0,30}[A-Za-z0-9]{35,}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Buildkite token",
        "regex_pattern": r"(?i)buildkite.{0,30}[A-Za-z0-9]{35,}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "SonarQube token",
        "regex_pattern": r"(?i)sonar.{0,30}[A-Za-z0-9]{35,}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Codecov token",
        "regex_pattern": r"(?i)codecov.{0,30}[A-Za-z0-9]{35,}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Cypress record key",
        "regex_pattern": r"(?i)cypress.{0,30}[A-Za-z0-9]{8}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{12}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "1Password service account token",
        "regex_pattern": r"\bops_[A-Za-z0-9]{64,}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Linear API key",
        "regex_pattern": r"\blin_api_[A-Za-z0-9]{40}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Pulumi access token",
        "regex_pattern": r"\bpul-[A-Za-z0-9]{40}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Terraform Cloud API token",
        "regex_pattern": r"\b[A-Za-z0-9]{14}\.atlasv1\.[A-Za-z0-9_\-]{67}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "LaunchDarkly SDK key",
        "regex_pattern": r"\bsdk-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "PlanetScale service token",
        "regex_pattern": r"\bpscale_tkn_[A-Za-z0-9_]{32,}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Fly.io token",
        "regex_pattern": r"\bfm1_[A-Za-z0-9_\-]{20,}\b",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
    {
        "name": "Netlify access token (context)",
        "regex_pattern": r"(?i)netlify.{0,30}[a-f0-9]{64}",
        "category": RegexCategory.DEVELOPMENT_TOOLS,
    },
]
