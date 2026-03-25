# Seed Data Plan

This document fixes the first implementation plan for local test data.

## Dataset Layers

### `tiny_seed`

Purpose:
- local frontend/backend integration
- schema checks
- manual query inspection

Target size:
- 50 to 200 products

Sources:
- hand-curated products from public metadata
- synthetic sellers, offers, and inventory

### `dev_seed`

Purpose:
- local search experiments
- index build testing
- retrieval quality inspection

Target size:
- 2,000 to 10,000 products

Sources:
- public product metadata
- public product images
- synthetic commerce fields

### `benchmark_seed`

Purpose:
- text / image / multimodal evaluation
- regression cases for retrieval and rerank

Target size:
- curated benchmark slice

## Source Split

### Public product metadata

Recommended:
- UCSD Amazon product metadata

Use for:
- title
- category
- brand
- descriptions
- rating and review aggregates when available

### Public product images

Recommended:
- Amazon Berkeley Objects

Use for:
- primary product images
- image embedding generation
- image retrieval testing

### Synthetic commerce fields

Generate locally for:
- sellers
- offers
- price
- currency
- inventory count
- product URLs

## Internal Normalized Output

Every seed source should normalize into:

- `categories`
- `products`
- `product_media`
- `sellers`
- `product_offers`
- `product_review_stats`
- `product_search_documents`
- `product_embeddings`

## First Execution Goal

The first seed implementation should load:

- 3 to 5 categories
- 2 to 3 sellers
- 100 products
- 1 primary image per product
- 1 text embedding placeholder per product
- 1 image embedding placeholder for products with images

## Current Implementation Status

The repository now includes:

- a deterministic `tiny_seed` builder based on the MVP catalog
- a PostgreSQL loader for:
  - `categories`
  - `products`
  - `product_media`
  - `sellers`
  - `product_offers`
  - `product_review_stats`
  - `product_search_documents`

The first loader intentionally skips `product_embeddings`.
Embeddings will be built in a later step after the core seed path is stable.
