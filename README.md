# Git-gud

A Django-based pipeline for discovering GitHub users, ingesting their commits and gists, indexing code content in Elasticsearch, and scanning for secrets using regex pattern matching. Built with a custom database-backed task queue for orchestrating multi-step ingestion workflows.

## Tech Stack

- **Python 3.14** / **Django 6.0**
- **PostgreSQL 16** — primary data store
- **Elasticsearch 8.16** — code content indexing and search
- **Kibana** — Elasticsearch visualization (available at port `5601`)
- **Docker Compose** — multi-service development environment

## Dev Container Setup

The project is designed to run inside a [Dev Container](https://containers.dev/). Opening it in VS Code or Cursor with the Dev Containers extension will automatically spin up the full stack.

### Services

| Service           | Description                                  | Port  |
|-------------------|----------------------------------------------|-------|
| **app**           | Django application container (workspace)     | 8000  |
| **worker**        | Background task worker (auto-starts)         | —     |
| **postgres**      | PostgreSQL 16 database                       | 5432  |
| **elasticsearch** | Elasticsearch 8.16.1 (single-node, no auth)  | 9200  |
| **kibana**        | Kibana dashboard                             | 5601  |

### Getting Started

1. Open the project in VS Code or Cursor.
2. When prompted, select **Reopen in Container** (or run the `Dev Containers: Reopen in Container` command).
3. Docker Compose builds and starts all services. The `post-create.sh` script automatically:
   - Waits for Postgres to be ready
   - Installs Python dependencies
   - Runs database migrations
   - Creates a superuser (`admin` / `admin`)
   - Seeds regex patterns for secret detection
4. The **worker** service starts automatically and begins polling for queued tasks.
5. Start the Django server using the **Django Server** launch configuration (F5), or manually:
   ```bash
   cd backend && python manage.py runserver 0.0.0.0:8000
   ```
6. Access the Django admin at [http://localhost:8000/admin/](http://localhost:8000/admin/) with `admin` / `admin`.

### GitHub API Tokens

Before running any tasks, add one or more GitHub personal access tokens via the Django admin under **GitHub Tokens**. The API client rotates through active tokens automatically when rate limits are hit.

## Task Pipeline

Tasks are enqueued through the Django admin and executed by the background worker. They should be run in the following order — each step depends on data produced by the previous one.

| #   | Task                     | Description                                                                                          |
|-----|--------------------------|------------------------------------------------------------------------------------------------------|
| 1   | **GitHub User Discovery**| Searches GitHub for users matching a query (with automatic date-range splitting to handle API limits). Requires a search query. |
| 2   | **Process Users**        | Expands discovered users — fetches their profiles, followers, following, and repository lists.         |
| 3   | **Process Repositories** | Fetches repository metadata, languages, and branches for tracked users.                               |
| 4   | **Process Gists**        | Ingests and indexes gist content for tracked users.                                                   |
| 5   | **Process Commits**      | Indexes commit content into Elasticsearch and the database.                                           |
| 6   | **Find Matches**         | Runs seeded regex patterns against indexed commits and gists to detect secrets (API keys, private keys, JWTs, cloud credentials, etc.). |
| 7   | **Get Raw Events**       | Ingests events from the GitHub Archive (GH Archive) into the events pipeline.                         |
| 8   | **Sync Event Commits**   | Syncs commits referenced by ingested events into the main commit processing flow.                     |

Tasks 1–6 form the core pipeline. Tasks 7–8 provide an alternative ingestion path via GH Archive data.

## Project Structure

```
backend/
├── apps/
│   ├── core/           # GitHub token management
│   ├── task_queue/     # Custom DB-backed task queue, worker, and all task definitions
│   ├── git_data/       # Models for users, repos, commits, gists, and relationships
│   ├── search/         # Regex patterns and match records for secret detection
│   └── events/         # GH Archive raw event ingestion
├── clients/            # GitHub API client with token rotation and rate limit handling
├── config/             # Django settings and URL configuration
└── manage.py
```
