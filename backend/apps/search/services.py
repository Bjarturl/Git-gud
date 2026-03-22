import logging

from django.conf import settings
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
from elasticsearch_dsl import analyzer, connections

logger = logging.getLogger(__name__)


code_analyzer = analyzer(
    "code_analyzer",
    tokenizer="whitespace",
    filter=["lowercase"],
)


class ElasticsearchService:
    def __init__(self):
        self._client = None
        self._index_name = settings.SEARCH_SETTINGS.get(
            "INDEX_NAME", "code_snippets")
        self._initialize_client()

    def _initialize_client(self):
        try:
            es_config = settings.ELASTICSEARCH_DSL["default"]
            self._client = Elasticsearch(
                hosts=es_config["hosts"],
                timeout=es_config.get("timeout", 20),
                max_retries=es_config.get("max_retries", 10),
                retry_on_timeout=es_config.get("retry_on_timeout", True),
            )

            connections.configure(
                default={
                    "hosts": es_config["hosts"],
                    "timeout": es_config.get("timeout", 20),
                    "max_retries": es_config.get("max_retries", 10),
                    "retry_on_timeout": es_config.get("retry_on_timeout", True),
                }
            )
        except Exception as exc:
            logger.error(f"Failed to initialize Elasticsearch client: {exc}")
            self._client = None

    def is_available(self):
        if not self._client:
            return False
        try:
            return self._client.ping()
        except Exception:
            return False

    def initialize_index(self):
        if not self.is_available():
            logger.warning(
                "Elasticsearch is not available, skipping index initialization")
            return False

        try:
            if self._client.indices.exists(index=self._index_name):
                logger.info(f"Index '{self._index_name}' already exists")
                return True

            index_body = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "analysis": {
                        "analyzer": {
                            "code_analyzer": {
                                "tokenizer": "whitespace",
                                "filter": ["lowercase"],
                            }
                        }
                    },
                },
                "mappings": {
                    "properties": {
                        "user": {"type": "keyword"},
                        "user_company": {"type": "text"},
                        "repo": {"type": "keyword"},
                        "repo_owner": {"type": "keyword"},
                        "repo_owner_company": {"type": "keyword"},
                        "source_id": {"type": "keyword"},
                        "message": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256,
                                }
                            },
                        },
                        "date": {"type": "date"},
                        "branch_name": {"type": "keyword"},
                        "filename": {"type": "keyword"},
                        "url": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "type": {"type": "keyword"},
                        "additions": {
                            "type": "text",
                            "analyzer": "code_analyzer",
                            "fields": {
                                "raw": {
                                    "type": "wildcard",
                                }
                            },
                        },
                        "deletions": {
                            "type": "text",
                            "analyzer": "code_analyzer",
                            "fields": {
                                "raw": {
                                    "type": "wildcard",
                                }
                            },
                        },
                    }
                },
            }

            response = self._client.indices.create(
                index=self._index_name,
                body=index_body,
            )

            logger.info(
                f"Successfully created index '{self._index_name}': {response}")
            return True

        except Exception as exc:
            logger.error(
                f"Failed to initialize index '{self._index_name}': {exc}")
            return False

    def index_document(self, doc_data, doc_id=None):
        if not self.is_available():
            return False

        try:
            response = self._client.index(
                index=self._index_name,
                id=doc_id,
                body=doc_data,
            )
            logger.debug(f"Indexed document {doc_id}: {response}")
            return response
        except Exception as exc:
            logger.error(f"Failed to index document {doc_id}: {exc}")
            return False

    def search(self, query, filters=None, size=50, from_=0, sort=None):
        if not self.is_available():
            return None

        try:
            body = {
                "query": self._build_search_query(query, filters),
                "size": size,
                "from": from_,
                "highlight": {
                    "fields": {
                        "additions": {
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"],
                            "fragment_size": 150,
                            "number_of_fragments": 3,
                        },
                        "deletions": {
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"],
                            "fragment_size": 150,
                            "number_of_fragments": 3,
                        },
                        "message": {
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"],
                            "fragment_size": 100,
                            "number_of_fragments": 1,
                        },
                    }
                },
            }

            if sort:
                body["sort"] = sort

            return self._client.search(
                index=self._index_name,
                body=body,
            )

        except Exception as exc:
            logger.error(f"Search failed: {exc}")
            return None

    def scan_documents(self):
        if not self.is_available():
            return

        try:
            yield from scan(
                self._client,
                index=self._index_name,
                query={"query": {"match_all": {}}},
            )
        except Exception as exc:
            logger.error(f"Scan failed: {exc}")
            return

    def scan_documents_from_timestamp(self, timestamp=None):
        if not self.is_available():
            return

        query = {"match_all": {}}

        if timestamp is not None:
            query = {
                "range": {
                    "timestamp": {
                        "gte": timestamp,
                    }
                }
            }

        body = {
            "query": query,
            "sort": [
                {"timestamp": "asc"},
            ],
        }

        try:
            count = 0
            for hit in scan(
                self._client,
                index=self._index_name,
                query=body,
                preserve_order=True,
            ):
                yield hit
                count += 1
        except Exception as exc:
            logger.error(f"Timestamp scan failed: {exc}")
            return

    def _build_search_query(self, query, filters=None):
        if not query and not filters:
            return {"match_all": {}}

        bool_query = {"bool": {"must": [], "filter": []}}

        if query:
            bool_query["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "additions^2",
                            "additions.raw",
                            "deletions^2",
                            "deletions.raw",
                            "message",
                            "filename",
                            "user",
                            "repo",
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }
            )

        if filters:
            for field, value in filters.items():
                if isinstance(value, list):
                    bool_query["bool"]["filter"].append(
                        {"terms": {field: value}})
                else:
                    bool_query["bool"]["filter"].append(
                        {"term": {field: value}})

        return bool_query

    def get_stats(self):
        if not self.is_available():
            return None

        try:
            stats = self._client.indices.stats(index=self._index_name)
            return {
                "total_docs": stats["indices"][self._index_name]["total"]["docs"]["count"],
                "size_bytes": stats["indices"][self._index_name]["total"]["store"]["size_in_bytes"],
                "index_name": self._index_name,
            }
        except Exception as exc:
            logger.error(f"Failed to get stats: {exc}")
            return None

    def delete_index(self):
        if not self.is_available():
            return False

        try:
            response = self._client.indices.delete(index=self._index_name)
            logger.info(f"Deleted index '{self._index_name}': {response}")
            return True
        except Exception as exc:
            logger.error(f"Failed to delete index: {exc}")
            return False

    def count_documents_from_timestamp(self, timestamp=None):
        if not self.is_available():
            return 0

        query = {"match_all": {}}

        if timestamp is not None:
            query = {
                "range": {
                    "timestamp": {
                        "gte": timestamp,
                    }
                }
            }

        try:
            response = self._client.count(
                index=self._index_name,
                body={"query": query},
            )
            return response.get("count", 0)
        except Exception as exc:
            logger.error(f"Count from timestamp failed: {exc}")
            return 0
