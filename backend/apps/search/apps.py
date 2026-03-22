from django.apps import AppConfig
import logging
from .services import ElasticsearchService


class SearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.search'

    def ready(self):
        try:
            elasticsearch_service = ElasticsearchService()
            if elasticsearch_service.is_available():
                elasticsearch_service.initialize_index()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not initialize Elasticsearch: {e}")
