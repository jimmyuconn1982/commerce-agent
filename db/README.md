# Database Workspace

This directory contains the first local database scaffolding for the project.

## Layout

- `init/`
  Files mounted into the Postgres container and executed on first boot.
- `migrations/`
  Versioned SQL schema files to apply manually or through a migration runner later.

## Current Scope

The current setup provides:

- PostgreSQL + `pgvector`
- extension bootstrap
- initial relational schema
- tiny-seed generation and loading entrypoints
- indexes for:
  - keyword search
  - trigram fallback search
  - vector search

## Apply the Initial Schema

Start the database:

```bash
docker compose up -d postgres
```

Apply the first migration:

```bash
docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0001_initial_schema.sql
```

If you are upgrading an existing local database from the older 1536-d mock vectors, apply:

```bash
docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0002_embedding_dimension_1024.sql
```

If you want the BigModel pipeline to use 2048-d embeddings, then apply:

```bash
docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0003_embedding_dimension_2048.sql
```

Note:
- the 2048-d path keeps vector similarity as a direct scan in local PostgreSQL
- pgvector HNSW indexes reject dimensions above 2000, so ANN indexes are disabled for this mode
- if you want local ANN indexes, stay on the 1024-d migration instead

Build the local tiny seed bundle:

```bash
commerce-agent-build-tiny-seed
```

Build a public 50-product seed bundle with image URLs and matching search text:

```bash
commerce-agent-build-public-seed
```

Load the tiny seed bundle:

```bash
commerce-agent-load-seed
```

Replace the current database contents with the public bundle:

```bash
commerce-agent-load-seed --seed-path db/seeds/public_seed_50.json --truncate-first
```

Build text embeddings:

```bash
commerce-agent-build-text-embeddings
```

Build image embeddings:

```bash
commerce-agent-build-image-embeddings
```

Build both local semantic indexes in one step:

```bash
commerce-agent-build-semantic-indexes
commerce-agent-semantic-index-status
```

Build semantic indexes with BigModel embeddings:

```bash
export COMMERCE_AGENT_EMBEDDING_PROVIDER=bigmodel
export BIGMODEL_API_KEY=YOUR_API_KEY
export BIGMODEL_EMBEDDING_MODEL=embedding-3
export BIGMODEL_EMBEDDING_DIMENSIONS=2048
commerce-agent-build-semantic-indexes
commerce-agent-semantic-index-status
```

Run PostgreSQL-backed text search:

```bash
commerce-agent-db-text-search "compact keyboard under 200"
```

## Next Steps

- add seed-data staging tables for public sources
- add import scripts for public and synthetic test data
- connect the real embedding and vision providers last
