-- Align embedding storage with provider-backed models configured for 2048-d vectors.
-- This migration resets existing embedding rows and requires rebuilding indexes after it runs.

BEGIN;

TRUNCATE TABLE product_embeddings;

DROP INDEX IF EXISTS idx_product_embeddings_text_vector;
DROP INDEX IF EXISTS idx_product_embeddings_image_vector;
DROP INDEX IF EXISTS idx_product_embeddings_multimodal_vector;

ALTER TABLE product_embeddings
    ALTER COLUMN embedding TYPE VECTOR(2048);

-- 2048-d vectors are kept without ANN indexes in local PostgreSQL because
-- pgvector HNSW indexes reject dimensions above 2000.

COMMIT;
