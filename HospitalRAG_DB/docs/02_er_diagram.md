# Module 2-3 — Database Design & Vector Schema

## High-Level Architecture

```text
                    User
                      │
                      ▼
                 FastAPI API
                      │
                      ▼
              Query Processing
                      │
                      ▼
              Embedding Model  (sentence-transformers, local -- or OpenAI)
                      │
                      ▼
          PostgreSQL + pgvector
                      │
          Vector Similarity Search (HNSW index, cosine distance)
                      │
                      ▼
          Retrieved Document Chunks
                      │
                      ▼
                  Prompt Builder
                      │
                      ▼
                     LLM  (local transformers -- or OpenAI)
                      │
                      ▼
               Final AI Response (+ citations)
```

## Entity-Relationship Diagram

```text
Departments
  │
  ├──< Users
  └──< HospitalDocuments ──< DocumentChunks
                                    │
                                    │ (retrieved by similarity search)
                                    ▼
Users ──< Conversations ──< Messages ──< MessageCitations >── DocumentChunks

Users ──< AuditLogs
```

Cardinalities:

- `Departments 1 --- * Users`, `Departments 1 --- * HospitalDocuments`
  (a document belongs to one department; a user's department is their
  primary scope, not an access-control boundary in this build — see
  Scope decisions)
- `HospitalDocuments 1 --- * DocumentChunks` (a document is split into
  many overlapping chunks at ingestion time)
- `Users 1 --- * Conversations 1 --- * Messages`
- `Messages 1 --- * MessageCitations * --- 1 DocumentChunks` (an
  assistant message cites zero or more chunks — zero exactly when
  retrieval found nothing relevant and the assistant said so)
- `Users 1 --- * AuditLogs`

## Normalization

Target: 3NF, same standard as the other two projects, with one
domain-specific exception:

- **`DocumentChunks.content` is a full copy of the chunk text**, not a
  byte-range reference into the source document. This looks
  denormalized (the source document's full text technically already
  contains it), but re-extracting a chunk's text from the original PDF
  on every retrieval would mean re-running text extraction on every
  question asked. Storing the chunk text is a cache with no staleness
  risk, because chunks are immutable once created — re-ingesting a
  changed document creates new chunk rows rather than editing old ones
  (see below).
- **Re-ingesting a document does not update existing chunks in place.**
  If a document's source content changes, ingestion creates a new set
  of chunks (new `content_hash` values); old chunks are only removed
  by explicit deletion. This is deliberate: a citation on a past
  answer should keep pointing at the chunk text that was actually
  retrieved when that answer was generated, the same "snapshot, not
  live lookup" argument used for `order_items.unit_price` in
  `mini_EcommerceDB` and for `grades` in `EMS_DB`.

## The vector column: a schema-time commitment

`document_chunks.embedding` is declared `vector(384)` — the output
dimension of the default local embedding model
(`sentence-transformers/all-MiniLM-L6-v2`). This is the single most
important constraint in this schema to understand:

- pgvector requires a **fixed dimension per column**, chosen when the
  table is created.
- Two different embedding models place vectors in *different,
  incompatible spaces* — cosine similarity between an OpenAI
  `text-embedding-3-small` vector (1536-dim) and a MiniLM vector
  (384-dim) isn't just inaccurate, it's not even computable; the
  dimensions don't match.
- **Switching `EMBEDDING_PROVIDER` after documents are already
  ingested does not retroactively fix anything.** Existing chunks keep
  their old vectors. Queries embedded with the new provider will be
  compared against vectors from the old one and retrieval quality
  silently degrades — no error, just worse answers. The fix is a real
  migration: alter the column's dimension and **re-embed every
  existing chunk**, not a config change.

This is why `EMBEDDING_PROVIDER` is read once at ingestion time and
recorded per chunk (`document_chunks.embedding_model`), so a mismatch
is at least detectable — see `scripts/reembed_check.py` referenced in
`docs/03_optimization.md`.

## Constraints summary

| Table | Key constraints |
|---|---|
| departments | PK; UNIQUE(name), UNIQUE(code) |
| users | PK; UNIQUE(email); FK department_id |
| hospital_documents | PK; FK department_id, uploaded_by; status ENUM; UNIQUE(file_hash) |
| document_chunks | PK; FK document_id; UNIQUE(content_hash) per document; `embedding vector(384) NOT NULL`; HNSW index on `embedding` |
| conversations | PK; FK user_id |
| messages | PK; FK conversation_id; role ENUM('user','assistant') |
| message_citations | PK(message_id, chunk_id); FK message_id, chunk_id |
| audit_logs | PK; FK user_id; action ENUM; `detail JSONB` |

## Advanced PostgreSQL used here

| Feature | Where |
|---|---|
| `pgvector` extension | `document_chunks.embedding vector(384)` |
| HNSW approximate-nearest-neighbor index | `idx_chunks_embedding_hnsw`, cosine ops |
| Vector similarity operator | `embedding <=> query_vector` (cosine distance) in `retriever_repository.py` |
| JSONB | `audit_logs.detail` (flexible per-action fields) |
| Full-text search (fallback path) | `document_chunks.content` — a plain keyword search path used when the retrieval evaluation harness compares semantic vs. lexical recall (Module 10) |

See `docs/03_optimization.md` for `EXPLAIN ANALYZE` evidence on the
HNSW index specifically — with vs. without it, at the chunk volumes
this project actually seeds.
