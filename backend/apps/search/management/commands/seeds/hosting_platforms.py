from apps.search.models import RegexCategory

SEEDS = [
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
]
