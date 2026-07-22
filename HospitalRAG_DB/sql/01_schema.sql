-- Hospital AI Knowledge Assistant schema
-- Module 2-3: Database Design + Vector Schema
-- Target: PostgreSQL 16+ with the pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------
CREATE TYPE user_role       AS ENUM ('staff', 'admin');
CREATE TYPE document_source AS ENUM ('pdf', 'txt', 'markdown');
CREATE TYPE document_status AS ENUM ('pending', 'processing', 'indexed', 'failed');
CREATE TYPE message_role    AS ENUM ('user', 'assistant');

-- ---------------------------------------------------------------------
-- Departments
-- ---------------------------------------------------------------------
CREATE TABLE departments (
    department_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    code          VARCHAR(20)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_departments_name UNIQUE (name),
    CONSTRAINT uq_departments_code UNIQUE (code)
);

-- ---------------------------------------------------------------------
-- Users (login-capable; demo-mode auth, see docs/01_requirements.md)
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id BIGINT REFERENCES departments(department_id) ON DELETE SET NULL,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          user_role    NOT NULL DEFAULT 'staff',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX idx_users_department ON users(department_id);

-- ---------------------------------------------------------------------
-- Hospital documents (the ingestion source)
-- ---------------------------------------------------------------------
CREATE TABLE hospital_documents (
    document_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    department_id     BIGINT REFERENCES departments(department_id) ON DELETE SET NULL,
    uploaded_by        BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    title              VARCHAR(255) NOT NULL,
    source_type        document_source NOT NULL,
    original_filename  VARCHAR(255) NOT NULL,
    -- SHA-256 of the raw uploaded file bytes. Catches a byte-identical
    -- re-upload before it's even extracted/chunked -- the chunk-level
    -- UNIQUE(document_id, content_hash) below only dedups *within* one
    -- document's own chunks (e.g. a retried ingestion), not across two
    -- separate uploads of the same file.
    file_hash          VARCHAR(64) NOT NULL,
    status             document_status NOT NULL DEFAULT 'pending',
    error_message      TEXT,
    uploaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at         TIMESTAMPTZ,
    CONSTRAINT uq_documents_file_hash UNIQUE (file_hash)
);

CREATE INDEX idx_documents_department ON hospital_documents(department_id);
CREATE INDEX idx_documents_status ON hospital_documents(status);

-- ---------------------------------------------------------------------
-- Document chunks -- the vector table.
--
-- vector(384) matches sentence-transformers/all-MiniLM-L6-v2, the
-- default local embedding model. This dimension is a schema-time
-- commitment -- see docs/02_er_diagram.md ("The vector column: a
-- schema-time commitment") for why switching embedding models later
-- requires a real migration, not a config change.
-- ---------------------------------------------------------------------
CREATE TABLE document_chunks (
    chunk_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     BIGINT NOT NULL REFERENCES hospital_documents(document_id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    token_count     INT NOT NULL,
    embedding       vector(384) NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    search_vector   tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_chunks_document_hash UNIQUE (document_id, content_hash)
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);

-- HNSW: approximate-nearest-neighbor index for cosine similarity search.
-- See docs/03_optimization.md for EXPLAIN ANALYZE evidence of what this
-- index buys (and costs) versus a sequential scan.
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Lexical fallback path, used by the evaluation harness (Module 10) to
-- compare semantic vs. keyword recall on the same chunk store.
CREATE INDEX idx_chunks_search ON document_chunks USING GIN (search_vector);

-- ---------------------------------------------------------------------
-- Conversations & messages
-- ---------------------------------------------------------------------
CREATE TABLE conversations (
    conversation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title           VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_user ON conversations(user_id);

CREATE TABLE messages (
    message_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role            message_role NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);

-- Which chunks backed a given (assistant) message, and in what rank
-- order they were retrieved -- the citation trail, and the raw material
-- the evaluation harness scores.
CREATE TABLE message_citations (
    message_id       BIGINT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    chunk_id         BIGINT NOT NULL REFERENCES document_chunks(chunk_id) ON DELETE CASCADE,
    rank             INT NOT NULL,
    similarity_score NUMERIC(6, 5) NOT NULL,
    PRIMARY KEY (message_id, chunk_id)
);

-- ---------------------------------------------------------------------
-- Audit log. `action` is a plain VARCHAR, not an ENUM -- unlike the
-- other status fields in this schema, the set of auditable actions is
-- expected to grow over the life of a real system, and an ENUM would
-- need a migration for every new action type.
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
    audit_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    action     VARCHAR(50) NOT NULL,
    detail     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_detail ON audit_logs USING GIN (detail);
