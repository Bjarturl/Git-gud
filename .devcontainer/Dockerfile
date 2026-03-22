FROM python:3.14-slim

# Install system dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  postgresql-client \
  curl \
  jq \
  gcc \
  git \
  gh \
  libpq-dev \
  netcat-openbsd \
  && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies for Django backend
COPY backend/pyproject.toml backend/pyproject.toml
RUN cd backend && pip install --upgrade pip && pip install -e ".[dev]"