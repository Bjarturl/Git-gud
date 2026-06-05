from . import (
    ai_tokens,
    api_and_webhooks,
    auth_headers,
    aws_infrastructure,
    cloud_keys_tokens,
    connection_strings_db,
    development_tools,
    docker_container_registry,
    hosting_platforms,
    jwt_tokens,
    messaging_communication,
    network_infrastructure,
    passwords_and_secrets_generic,
    payment_financial,
    private_keys,
    social_media_apis,
    urls_general,
    usernames,
)

ALL_SEEDS = (
    ai_tokens.SEEDS
    + api_and_webhooks.SEEDS
    + auth_headers.SEEDS
    + aws_infrastructure.SEEDS
    + cloud_keys_tokens.SEEDS
    + connection_strings_db.SEEDS
    + development_tools.SEEDS
    + docker_container_registry.SEEDS
    + hosting_platforms.SEEDS
    + jwt_tokens.SEEDS
    + messaging_communication.SEEDS
    + network_infrastructure.SEEDS
    + passwords_and_secrets_generic.SEEDS
    + payment_financial.SEEDS
    + private_keys.SEEDS
    + social_media_apis.SEEDS
    + urls_general.SEEDS
    + usernames.SEEDS
)
