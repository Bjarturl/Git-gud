from apps.search.models import RegexCategory

SEEDS = [
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
]
