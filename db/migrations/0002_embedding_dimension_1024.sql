-- Align embedding storage with provider-backed models that output 1024-d vectors.
-- This migration resets existing embedding rows and requires rebuilding indexes after it runs.

BEGIN;

TRUNCATE TABLE product_embeddings;

DROP INDEX IF EXISTS idx_product_embeddings_text_vector;
DROP INDEX IF EXISTS idx_product_embeddings_image_vector;
DROP INDEX IF EXISTS idx_product_embeddings_multimodal_vector;

ALTER TABLE product_embeddings
    ALTER COLUMN embedding TYPE VECTOR(1024);

CREATE INDEX IF NOT EXISTS idx_product_embeddings_text_vector
    ON product_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding_type = 'text';

CREATE INDEX IF NOT EXISTS idx_product_embeddings_image_vector
    ON product_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding_type = 'image';

CREATE INDEX IF NOT EXISTS idx_product_embeddings_multimodal_vector
    ON product_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding_type = 'multimodal';

COMMIT;
