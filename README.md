# commerce-agent

Minimal Python `commerce_agent` focused on chat and retrieval. It supports:

- chat-style product guidance
- text search
- image search from a real uploaded image
- text + image multimodal search
- automatic backend intent routing for chat, text, image, and multimodal inputs
- a CLI entrypoint for local usage
- a web UI with simulated users and persistent chat histories

## Quick start

```bash
python3 -m pip install -e .
commerce-agent chat "I want a compact keyboard for my desk"
commerce-agent text-search keyboard
commerce-agent-web
```

## Commands

```bash
commerce-agent chat "Find something that looks like this" --image ./example.jpg
commerce-agent text-search "running shoes" --category footwear
commerce-agent image-search ./example.jpg
commerce-agent multimodal-search --text "office" --image ./example.jpg
```

Image retrieval now uses a real vision step through the OpenAI Responses API. The agent reads a local image file, sends it as a Base64 data URL for image understanding, then reranks the catalog using the returned summary and tags.

Set `OPENAI_API_KEY` before using `image-search`, `multimodal-search --image ...`, or `chat --image ...`.

If you want to test the image pipeline without a real API key, enable mock vision mode:

```bash
COMMERCE_AGENT_MOCK_VISION=1 commerce-agent-web
```

Optional custom mock response:

```bash
COMMERCE_AGENT_MOCK_VISION=1 \
COMMERCE_AGENT_MOCK_VISION_RESPONSE=$'summary: compact green bag\ntags: bag, green, compact, accessory, leather' \
commerce-agent-web
```

## Web UI

Run:

```bash
commerce-agent-web
```

Then open `http://127.0.0.1:8000`.

If port `8000` is occupied, run with another port:

```bash
COMMERCE_AGENT_PORT=8010 commerce-agent-web
```

The web UI includes:

- a single conversation box with automatic intent routing
- predefined simulated users
- multiple chat threads per user
- browser-persisted chat history across refreshes

## Design Docs

- Database design and ER diagram: [docs/database-design.md](docs/database-design.md)
- 数据库设计与 ER 图: [docs/database-design.zh-CN.md](docs/database-design.zh-CN.md)
- Seed data plan: [docs/seed-data-plan.md](docs/seed-data-plan.md)

## Local Database

Start PostgreSQL with `pgvector`:

```bash
docker compose up -d postgres
```

Apply the initial schema:

```bash
docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0001_initial_schema.sql
```

The database workspace lives in [db/README.md](db/README.md).

Build and load the tiny local seed:

```bash
commerce-agent-build-tiny-seed
commerce-agent-load-seed
commerce-agent-build-public-seed
commerce-agent-load-seed --seed-path db/seeds/public_seed_50.json --truncate-first
commerce-agent-build-text-embeddings
commerce-agent-build-image-embeddings
commerce-agent-build-semantic-indexes
commerce-agent-semantic-index-status
commerce-agent-db-text-search "compact keyboard under 200"
python -m devtools.evalbench.runner --suite all
```

The web UI now includes an in-page pipeline debug panel for assistant results. It shows the routed intent, tool steps, retrieval candidates, and score summaries without leaving the browser.
