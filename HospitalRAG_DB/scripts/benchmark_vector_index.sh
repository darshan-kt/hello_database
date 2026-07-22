#!/usr/bin/env bash
# Reproduces the HNSW benchmark from docs/03_optimization.md yourself:
# inserts 20,000 synthetic vectors, runs the same similarity search with
# and without the index, then cleans up after itself. Read alongside
# docs/03_optimization.md Section 1.
set -euo pipefail

CONTAINER="${PG_CONTAINER:-rag_postgres}"
PSQL="docker exec -i $CONTAINER psql -U rag_app -d hospital_rag"

echo "==> Inserting a throwaway document to hold 20,000 synthetic chunks..."
DOC_ID=$($PSQL -tAc "
INSERT INTO hospital_documents (title, source_type, original_filename, file_hash, status)
VALUES ('Benchmark Synthetic Doc', 'txt', 'bench.txt', md5(random()::text), 'indexed')
RETURNING document_id;
" | head -1)

echo "==> Generating 20,000 random 384-dim vectors (takes ~10-15s)..."
$PSQL -c "
INSERT INTO document_chunks (document_id, chunk_index, content, content_hash, token_count, embedding, embedding_model)
SELECT $DOC_ID, gs, 'synthetic benchmark chunk ' || gs, md5(gs::text || random()), 5,
       (SELECT array_agg(random())::vector(384) FROM generate_series(1,384)),
       'benchmark'
FROM generate_series(1, 20000) gs;
"
$PSQL -c "ANALYZE document_chunks;"

echo
echo "==> WITH the HNSW index:"
$PSQL -c "
EXPLAIN ANALYZE
SELECT chunk_id, 1 - (embedding <=> (SELECT embedding FROM document_chunks WHERE chunk_id = (SELECT MIN(chunk_id) FROM document_chunks))) AS similarity
FROM document_chunks
ORDER BY embedding <=> (SELECT embedding FROM document_chunks WHERE chunk_id = (SELECT MIN(chunk_id) FROM document_chunks))
LIMIT 5;
"

echo "==> Dropping the index..."
$PSQL -c "DROP INDEX idx_chunks_embedding_hnsw;"

echo "==> WITHOUT the index (sequential scan + full sort):"
$PSQL -c "
EXPLAIN ANALYZE
SELECT chunk_id, 1 - (embedding <=> (SELECT embedding FROM document_chunks WHERE chunk_id = (SELECT MIN(chunk_id) FROM document_chunks))) AS similarity
FROM document_chunks
ORDER BY embedding <=> (SELECT embedding FROM document_chunks WHERE chunk_id = (SELECT MIN(chunk_id) FROM document_chunks))
LIMIT 5;
"

echo "==> Recreating the index and cleaning up the synthetic data..."
$PSQL -c "CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);"
$PSQL -c "DELETE FROM hospital_documents WHERE document_id = $DOC_ID;"
$PSQL -c "VACUUM FULL document_chunks;"
$PSQL -c "ANALYZE document_chunks;"

echo
echo "Done -- back to the real seeded corpus, index restored. Compare your numbers to docs/03_optimization.md."
