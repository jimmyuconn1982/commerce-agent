# commerce-agent

`commerce-agent` is a local-first commerce search agent with:

- scoped chat
- text product search
- image product search
- multimodal product search
- LLM-based intent routing
- PostgreSQL + `pgvector` retrieval
- a chat-style web UI
- a dedicated backend debug GUI
- a storefront-style product detail page

## Current Status

Latest local verification on **March 25, 2026**:

- `pytest -q`: **63 passed**
- local PostgreSQL seed: **50 products**
- semantic indexes:
  - `text_embeddings = 50`
  - `image_embeddings = 50`
  - `multimodal_embeddings = 50`

Provider note:

- the implementation is not conceptually tied to BigModel only
- the current tested setup in this repository uses **BigModel**
- for model-backed routing / chat / metadata / vision, the practical expectation is an **OpenAI-compatible API shape**
- README examples below therefore use BigModel environment variables because that is the provider actually validated in this repo right now

## Pages

Main chat UI:

- `/`
- chat + text search + image search + multimodal search in one input box
- pending state while searching
- optional in-page debug toggle

Backend debug GUI:

- `/debug`
- seed database explorer
- product inspector
- search lab
- pipeline trace
- routed intent
- top candidates
- LLM context
- text/image/multimodal score breakdown

Storefront-style product page:

- `/products/{sku}`
- renders one product as an ecommerce detail page

## Screenshots

Main frontend:

![Main frontend](docs/screenshots/frontend-home.png)

Backend debug GUI:

![Debug GUI](docs/screenshots/debug-gui.png)

Storefront-style product page:

![Product page](docs/screenshots/product-page.png)

Search outcomes:

![Search outcomes](docs/screenshots/search-outcomes.png)

## Features

- One unified message endpoint: backend decides `chat`, `text-search`, `image-search`, or `multimodal-search`
- Search paths use database-backed retrieval instead of the old in-memory catalog path
- Retrieval uses three semantic channels:
  - text semantic retrieval
  - image semantic retrieval
  - multimodal semantic retrieval
- Candidates are fused, reranked, and then sent to an LLM for the final grounded answer
- Final UI cards only show the products selected by the LLM

## Deliverables Checklist

This repository currently covers the requested deliverables:

- User-friendly frontend interface
  - chat-style web UI at `/`
  - optional debug toggle
  - product detail page at `/products/{sku}`
- Documented agent API
  - unified runtime API and debug API documented below
  - typed response models in [src/commerce_agent/api_models.py](src/commerce_agent/api_models.py)
- Code repository with README
  - English README: [README.md](README.md)
  - Chinese README: [README.zh-CN.md](README.zh-CN.md)

## Technology Decisions

This project intentionally uses a simple stack that is easy to demo, inspect, and evolve:

- **FastAPI**
  - small, explicit HTTP surface
  - easy multipart handling for text + image requests
  - easy to expose debug endpoints alongside the main API
- **PostgreSQL + pgvector**
  - one database for structured product data and vector retrieval
  - easy joins across products, media, offers, sellers, and review stats
  - good fit for local development and demo deployment
- **Model-backed routing / enrichment / generation**
  - small model for intent routing
  - model-backed metadata enrichment during seed build
  - grounded final response generation from reranked products
- **Render Free for demo hosting**
  - minimal ops for a one-user demo
  - easy public URL sharing
  - acceptable tradeoff despite cold starts and 30-day free Postgres expiry

These choices optimize for:

- demoability
- backend observability
- grounded retrieval behavior
- low deployment friction

## Technical Implementation Path

The current backend path is:

1. unified request entry
2. LLM-backed intent routing
3. optional image understanding
4. retrieval from PostgreSQL
5. three-channel score fusion
6. rerank
7. LLM-grounded final answer
8. UI renders only LLM-selected products

Main modules:

- routing: [src/commerce_agent/router.py](src/commerce_agent/router.py)
- orchestration: [src/commerce_agent/agent.py](src/commerce_agent/agent.py)
- repository: [src/commerce_agent/repository.py](src/commerce_agent/repository.py)
- embeddings: [src/commerce_agent/embeddings.py](src/commerce_agent/embeddings.py)
- seed pipeline: [src/commerce_agent/seed_data.py](src/commerce_agent/seed_data.py)
- search final generation: [src/commerce_agent/search_responder.py](src/commerce_agent/search_responder.py)
- web API: [src/commerce_agent/web.py](src/commerce_agent/web.py)

## Data Sourcing and Cleaning

Current local seed strategy is intentionally split into 2 layers:

1. public product source
2. normalized local commerce schema

The project currently uses public product rows fetched from `DummyJSON` for the 50-product local seed. During seed build, the pipeline:

- fetches public product rows with:
  - title
  - description
  - category
  - price
  - rating
  - stock
  - tags
  - brand
  - sku
  - images / thumbnail
  - reviews
- normalizes categories and seller codes
- maps source rows into internal tables:
  - `products`
  - `product_media`
  - `sellers`
  - `product_offers`
  - `product_review_stats`
  - `product_search_documents`
- generates stable ids through the shared id module
- enriches retrieval-oriented metadata through an LLM-backed metadata enricher

Relevant implementation:

- public fetch + normalization: [src/commerce_agent/seed_data.py](src/commerce_agent/seed_data.py)
- id generation: [src/commerce_agent/ids.py](src/commerce_agent/ids.py)
- centralized DB writes: [src/commerce_agent/db_write.py](src/commerce_agent/db_write.py)

## Metadata Enrichment

The project no longer relies on a fixed handwritten grocery-term map as the primary path.

Instead, during seed build, product metadata is enriched by a model-backed step:

- input:
  - title
  - description
  - category
  - tags
  - brand
- output:
  - `search_terms`
  - `cooking_uses`
  - `audience_terms`

This enrichment is used to make retrieval more robust when the source dataset has weak structured metadata.

Current implementation:

- enricher interface and provider-backed implementation:
  - [src/commerce_agent/seed_data.py](src/commerce_agent/seed_data.py)

Fallback behavior still exists, but only as a safety net when the provider is unavailable.

## Retrieval Pipeline

For search requests, the system does not rely on a single retrieval channel.

All retrieval paths now use **three semantic channels**:

- `text` semantic retrieval
- `image` semantic retrieval
- `multimodal` semantic retrieval

### Text query path

For text requests, the backend:

- parses the query with the lightweight search parser
- embeds the text query
- derives an image-side reference embedding from the same query text
- derives a multimodal embedding query from the same query text
- queries PostgreSQL `product_embeddings` for:
  - `embedding_type = 'text'`
  - `embedding_type = 'image'`
  - `embedding_type = 'multimodal'`
- unions candidates and computes a fused score

### Image query path

For image requests, the backend:

- runs image understanding first
- converts image summary + image tags into query text
- builds:
  - text-side semantic vector
  - image-side semantic vector
  - multimodal semantic vector
- queries the same 3 embedding families in PostgreSQL

### Multimodal query path

For text + image requests, the backend:

- parses the text query
- runs image understanding
- combines both into a shared multimodal query representation
- retrieves from all 3 embedding families

This means:

- text search is not “text only”
- image search is not “image only”
- multimodal search is not “just one blended vector”

Each path retrieves across all 3 semantic spaces, then fuses results.

## Score Fusion and Rerank

The current repository computes a fused match score from the 3 semantic channels.

Current weighting:

- text-search:
  - text: `0.4`
  - image: `0.2`
  - multimodal: `0.4`
- image-search:
  - text: `0.2`
  - image: `0.45`
  - multimodal: `0.35`
- multimodal-search:
  - text: `0.3`
  - image: `0.3`
  - multimodal: `0.4`

Then the agent applies rerank over the shared `ScoredCandidate` shape. The current rerank layer can sort by:

- `text-score`
- `image-score`
- `multimodal-score`
- `blended-score`

The debug GUI exposes:

- text semantic score
- image semantic score
- multimodal semantic score
- fused score

Relevant implementation:

- SQL retrieval and fusion: [src/commerce_agent/repository.py](src/commerce_agent/repository.py)
- rerank layer: [src/commerce_agent/agent.py](src/commerce_agent/agent.py)
- debug GUI: [web/debug.html](web/debug.html), [web/assets/debug.js](web/assets/debug.js)

## Final LLM Answer Generation

The final answer shown to the user is not a raw dump of the top-k candidates.

The current flow is:

1. retrieval produces top-k candidates
2. rerank orders them
3. the reranked set is sent to the search responder
4. the LLM returns:
   - `response`
   - `selected_product_ids`
5. the UI only shows products whose ids were selected by the LLM

This is important because weak candidates may still exist in retrieval top-k, but they should not necessarily be shown to the user.

The debug trace exposes:

- `selected_product_ids`
- `prompt_context`
- top candidates before final selection

Relevant implementation:

- [src/commerce_agent/search_responder.py](src/commerce_agent/search_responder.py)
- [src/commerce_agent/tools.py](src/commerce_agent/tools.py)
- [web/assets/app.js](web/assets/app.js)

## Performance Optimization Opportunities

Current implementation is correct for local development, but there are several clear optimization paths.

### Data and indexing

- make semantic indexing incremental instead of full rebuild
- add source hash tracking for:
  - text embedding inputs
  - image embedding inputs
  - multimodal embedding inputs
- separate “changed products” from “full rebuild”

### Retrieval quality

- add category-aware retrieval boosts
- add explicit exclusion signals for:
  - pet food vs human food
  - decor vs furniture vs kitchen
- add better multilingual query rewriting before embedding
- expand parser from light rules to model-backed structured query parsing

### Retrieval efficiency

- tune candidate pool sizes per channel instead of fixed `limit * 8`
- use ANN-specific tuning for `pgvector` HNSW indexes
- cache query embeddings for repeated searches
- batch embedding generation during build jobs

### Rerank quality

- introduce a dedicated rerank model instead of score-only rerank
- add price / inventory / review-aware business rerank features
- support intent-specific rerank templates

### LLM final generation

- add explicit citations from selected products
- persist raw LLM output in debug mode
- keep structured JSON output contract strict and validated
- add response grounding checks in evalbench

### Debug and observability

- expose raw retrieval SQL timing
- expose per-channel candidate counts
- show “selected before validation / selected after validation”
- log provider/model versions in every trace

## Project Docs

- English database design: [docs/database-design.md](docs/database-design.md)
- 中文数据库设计: [docs/database-design.zh-CN.md](docs/database-design.zh-CN.md)
- Seed data plan: [docs/seed-data-plan.md](docs/seed-data-plan.md)
- 中文说明: [README.zh-CN.md](README.zh-CN.md)
- Database workspace: [db/README.md](db/README.md)

## Local Setup

### Option A: install from `pyproject.toml`

```bash
python3 -m pip install -e .
```

### Option B: install from `requirements.txt`

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

### Environment

Copy the local config template:

```bash
cp .env.example .env
```

Typical local keys:

- `BIGMODEL_API_KEY`
- `COMMERCE_AGENT_VISION_API_KEY`
- `OPENAI_API_KEY`

Important clarification:

- the code path is currently tested with **BigModel**
- the runtime model/provider configuration is centralized and can be changed
- the provider side should expose an OpenAI-style chat / embedding interface if you want to swap it cleanly
- in other words: the examples below use BigModel because that is what has been verified, not because the overall architecture must be BigModel-only

Important config is centralized in:

- [src/commerce_agent/config.py](src/commerce_agent/config.py)

## Documented Agent API

The backend exposes one main user-facing API plus several debug endpoints.

### Main runtime API

#### `POST /api/message`

Unified chat/search entrypoint.

Form fields:

- `text`: optional text prompt
- `file`: optional local image upload
- `image_url`: optional remote image URL
- `limit`: optional integer, default `10`

Behavior:

- routes to `chat`, `text-search`, `image-search`, or `multimodal-search`
- returns the grounded answer plus selected products

Example:

```bash
curl -X POST http://127.0.0.1:8010/api/message \
  -F 'text=I need fruit' \
  -F 'limit=5'
```

Response shape:

- `intent`
- `content`
- `analysis`
- `matches`
- `trace`
- `limit`

Schema:

- [src/commerce_agent/api_models.py](src/commerce_agent/api_models.py)

#### `GET /api/products/{product_ref}`

Return one product detail page payload by `sku` or numeric id.

Example:

```bash
curl http://127.0.0.1:8010/api/products/GRO-BRD-APP-016
```

### Debug API

#### `GET /api/debug/seed-summary`

Return row counts for:

- categories
- products
- product media
- search docs
- text embeddings
- image embeddings
- multimodal embeddings

#### `GET /api/debug/products`

Return joined product rows for the debug explorer.

Query parameters:

- `limit`: optional, max `500`

#### `GET /api/debug/products/{product_ref}`

Return one fully joined debug product payload by `sku` or numeric id.

#### `POST /api/debug/run`

Run the same pipeline as `/api/message`, but intended for the debug GUI.

Form fields:

- `text`
- `file`
- `image_url`
- `limit`

This endpoint returns the full pipeline trace that the debug page renders.

## Database Setup

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Apply migrations:

```bash
docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0001_initial_schema.sql

docker compose exec -T postgres psql \
  -U commerce_agent \
  -d commerce_agent \
  -f /work/db/migrations/0002_embedding_dimension_1024.sql
```

## Seed and Index Build

Build and load the public 50-product seed:

```bash
commerce-agent-build-public-seed
commerce-agent-load-seed --seed-path db/seeds/public_seed_50.json --truncate-first
```

Build semantic indexes:

```bash
commerce-agent-build-semantic-indexes
commerce-agent-semantic-index-status
```

Build one index family only:

```bash
commerce-agent-build-text-embeddings
commerce-agent-build-image-embeddings
commerce-agent-build-multimodal-embeddings
```

The commands above are provider-agnostic from the CLI perspective. In the current repository, the validated configuration uses BigModel-backed embeddings.

## Run the App

CLI examples:

```bash
commerce-agent chat "What kinds of search do you support?"
commerce-agent text-search "running shoes"
commerce-agent image-search ./example.jpg
commerce-agent multimodal-search --text "office chair" --image ./example.jpg
```

Start the web UI:

```bash
commerce-agent-web
```

If port `8000` is occupied:

```bash
COMMERCE_AGENT_PORT=8010 commerce-agent-web
```

Then open:

- `http://127.0.0.1:8010/`
- `http://127.0.0.1:8010/debug`

## Deploy to Render Free

For a one-user demo, the simplest hosted option in this repo is a Render Blueprint.

Included deployment assets:

- [render.yaml](render.yaml)
- [Dockerfile](Dockerfile)
- [src/commerce_agent/deploy.py](src/commerce_agent/deploy.py)

What the Blueprint does:

- creates one free Render web service
- creates one free Render Postgres instance
- runs a startup bootstrap command on first launch:
  - applies PostgreSQL extensions
  - applies schema migrations
  - fetches and writes the 50-product public seed
  - loads the seed into the database
  - builds text, image, and multimodal semantic indexes

### Render Free limitations

- the free web service can spin down after inactivity, so the first request may be slow
- the free Render Postgres instance has a 30-day limit
- this is suitable for demo use, not a durable production environment

### Deploy steps

1. Push this repo to GitHub
2. In Render, create a new Blueprint and point it to this repository
3. Render will read [render.yaml](render.yaml)
4. When prompted, fill in:
   - `BIGMODEL_API_KEY`
   - optionally:
     - `COMMERCE_AGENT_CHAT_API_KEY`
     - `COMMERCE_AGENT_VISION_API_KEY`
     - `COMMERCE_AGENT_METADATA_API_KEY`
5. Wait for the initial deploy to finish

On the first successful app start, the service runs:

```bash
commerce-agent-render-start
```

That command checks whether the database is already initialized. If not, it runs the full bootstrap once and then starts the web app.

The app should then be available at:

- `/`
- `/debug`
- `/products/{sku}`

## Docker Deployment

Current repo includes Dockerized PostgreSQL for local development:

```bash
docker compose up -d postgres
```

A typical local run flow is:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U commerce_agent -d commerce_agent -f /work/db/migrations/0001_initial_schema.sql
docker compose exec -T postgres psql -U commerce_agent -d commerce_agent -f /work/db/migrations/0002_embedding_dimension_1024.sql
commerce-agent-build-public-seed
commerce-agent-load-seed --seed-path db/seeds/public_seed_50.json --truncate-first
commerce-agent-build-semantic-indexes
COMMERCE_AGENT_PORT=8010 commerce-agent-web
```

If you want a containerized app image as well, this repo also includes:

- [Dockerfile](Dockerfile)

## Test Commands

Run the full test suite:

```bash
pytest -q
```

Run focused suites:

```bash
pytest -q tests/test_web.py
pytest -q tests/test_agent.py
```

Run the eval bench:

```bash
python -m devtools.evalbench.runner --suite all
```

## Debug GUI Highlights

The backend debug GUI is one of the core workflows in this repo.

What it shows:

- seed database row counts
- searchable products from PostgreSQL
- text tags
- image tags
- search terms
- cooking-use metadata
- embedding coverage
- one-product inspector
- search lab for live requests
- intent routing result
- top candidates
- rerank output
- LLM context sent for final answer generation

## Provider Configuration Notes

This repository currently demonstrates and validates the following model-backed paths with **BigModel**:

- intent router
- metadata enrichment
- search final answer generation
- vision understanding
- embeddings

That does **not** mean the product design requires BigModel only.

What is actually important:

- provider settings are centralized in [src/commerce_agent/config.py](src/commerce_agent/config.py)
- model-backed steps are selected through environment variables
- the provider should support the same kind of API contract the code expects

So the README examples intentionally show BigModel because that is the provider tested here, while the architecture remains configurable.

## Notes

- Product detail links now prefer `sku`, not unstable internal numeric ids
- The final search answer is LLM-grounded, but constrained to the retrieved database products
- If search returns weak candidates, they may still appear in debug top-k, but the final UI cards are filtered by the LLM-selected product ids
