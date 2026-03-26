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

## Write Path Policy

Application-owned database writes must go through [src/commerce_agent/db_write.py](../src/commerce_agent/db_write.py).

Current code paths already using the shared writer:
- seed loading
- semantic index builds

Future product ingest, admin writes, and background sync jobs should extend this module instead of issuing ad-hoc SQL writes elsewhere.

You can run the policy check locally with:

```bash
python scripts/check_db_write_policy.py
```

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

If you want the BigModel pipeline to stay compatible with pgvector HNSW indexes, then apply:

```bash
docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0004_embedding_dimension_1024_hnsw.sql
```

Note:
- `HNSW` is the approximate-nearest-neighbor graph index used by pgvector for fast vector lookup
- pgvector HNSW rejects dimensions above 2000
- BigModel `embedding-3` supports `256 / 512 / 1024 / 2048`, not `1536`
- the practical BigModel + HNSW choice is `1024`

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
export BIGMODEL_EMBEDDING_DIMENSIONS=1024
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
