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

## Next Steps

- add seed-data staging tables
- add import scripts for public and synthetic test data
- connect the backend repository layer to PostgreSQL
