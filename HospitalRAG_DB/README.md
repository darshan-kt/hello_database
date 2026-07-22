# Hospital AI Knowledge Assistant (RAG)

The third project in this repo's database-learning series, and a
genre change from the first two: a Retrieval-Augmented Generation
system. Instead of a bare LLM answering from its pretrained knowledge,
this assistant retrieves relevant chunks from the hospital's own
documents (via PostgreSQL + **pgvector**) and answers only from that
retrieved context — with citations, and an honest "I don't know" when
nothing relevant exists.

Built to the milestone curriculum in
[`../docs/4.Hospital_AI_Knowledge_Assistant_RAG_Roadmap.md`](../docs/4.Hospital_AI_Knowledge_Assistant_RAG_Roadmap.md)
(see `docs/01_requirements.md` for the exact scope, including what was
deliberately cut from the original brief and why): requirements →
domain modeling → relational + vector schema → a layered Python
backend → document ingestion (extract → chunk → embed → store) →
semantic retrieval → prompt construction → LLM generation → a chat UI
→ an evaluation harness → tests → `EXPLAIN ANALYZE` on the vector
index.

Everything — Postgres+pgvector, the backend, and the web UI — runs
from a single `docker compose up`. **No API key required.** The
default embedding model and LLM both run locally, on CPU, inside the
backend container.

![Walkthrough: staff asks a grounded question, sees citations, gets an honest "I don't know" for an out-of-scope question, admin manages documents and runs the evaluation harness](docs/screenshots/walkthrough.gif)

## Quickstart (Docker only)

```bash
cd HospitalRAG_DB
make up      # or: docker compose up -d --build
make seed    # ingests 6 real sample hospital documents (idempotent -- safe to re-run)
```

| Service    | What it is                                              | URL                          |
|------------|------------------------------------------------------------|--------------------------------|
| `postgres` | PostgreSQL 16 + pgvector, schema loaded on first boot       | `localhost:5434` (for a DB client) |
| `backend`  | FastAPI + the web UI (static files served by the same app) | **http://localhost:5002**    |

Open **http://localhost:5002**. **Login is demo mode**: any
email/password logs you in as either role, and an unrecognized email
auto-creates an account (same pattern as `mini_EcommerceDB` and
`EMS_DB`). Two accounts come pre-seeded with real history:

| Role | Email | Notes |
|---|---|---|
| Staff | `demo.staff@hospital.test` | Has real conversation history |
| Admin | `admin@hospital.test` | Manages documents/departments, runs the evaluation harness |

**Be patient with the first question you ask** — the local LLM
(`Qwen/Qwen2.5-0.5B-Instruct`) downloads (~1GB) and loads into memory
on first use, which can take up to ~90 seconds on CPU. After that,
answers take roughly 10-15 seconds each. This is the honest cost of
"zero setup, zero API keys" — see "Using a real LLM instead" below to
trade that for speed and quality.

## Learn it interactively (Makefile)

```bash
make demo               # watch the full lifecycle happen, narrated (real LLM call, be patient)
make db-shell            # then go look at the embeddings/chunks yourself
make explain              # EXPLAIN ANALYZE at real seeded scale
make benchmark-vector-index  # reproduce the HNSW-index-at-scale evidence from docs/03_optimization.md yourself
```

Full guided tour, staged from "look at the schema" through embeddings,
chunking, vector search, the no-hallucination guard, and the
evaluation harness: **[`docs/04_interactive_learning.md`](docs/04_interactive_learning.md)**.

## Using the UI

**As staff** (log in with the demo account, or type any email):
1. Ask a question in the chat box — try *"What is the treatment
   protocol for dengue fever?"*. The answer streams in as a "Thinking…"
   bubble, then shows with an expandable **N sources** panel citing the
   exact document chunks and similarity scores used.
2. Ask something the documents don't cover — try *"What is the capital
   of France?"* — and see the assistant say it doesn't know, instead
   of guessing.
3. Ask a follow-up in the same conversation. Keep the topic named (see
   the "Known limitation" note in `docs/01_requirements.md` for why a
   bare pronoun-only follow-up can retrieve nothing).
4. **New conversation** starts a fresh thread; the sidebar lists your
   history.

**As admin** (`admin@hospital.test`):
1. **Documents** — upload a `.pdf`, `.txt`, or `.md` file, watch it go
   through ingestion, see its status (`pending` → `processing` →
   `indexed`/`failed`). Try uploading the exact same file twice.
2. **Departments** — add one; documents and retrieval can be scoped to
   a department.
3. **Evaluation** — run the Module 10 harness: semantic vs. lexical
   recall/precision against a hand-labeled question set.
4. **Audit Log** — every question asked and document uploaded, with
   who and when.

### What each screenshot demonstrates

| Screenshot | Shows |
|---|---|
| `docs/screenshots/04_chat_answer.png` | A grounded answer to a real clinical question |
| `docs/screenshots/05_chat_citations.png` | Expanded citations: which chunks, which documents, similarity scores |
| `docs/screenshots/06_chat_no_context.png` | The "I don't know" guard for an out-of-scope question |
| `docs/screenshots/08_admin_documents.png` | Document ingestion status |
| `docs/screenshots/10_admin_evaluation.png` | Real evaluation harness output: 100% semantic recall, 50% lexical |

## Using a real LLM instead

Everything above runs with zero configuration. To swap in OpenAI for
faster, higher-quality answers, create a `.env` (see `.env.example`):

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Embeddings can be switched independently
(`EMBEDDING_PROVIDER=openai`) — OpenAI's `text-embedding-3-small` is
requested with `dimensions=384` specifically so it fits the existing
schema without a migration (see "Key design decisions" below for why
that's not usually possible for free). Restart with
`docker compose up -d --build` after editing `.env`.

## Running the tests (also Docker-only)

```bash
make test
```

Runs `pytest` inside the same image as the backend, against the real
Postgres+pgvector. The suite injects a `FakeLLMProvider`
(`tests/conftest.py`) so it never makes a real, slow model call — it's
fast and deterministic, while still exercising the real embedding
model and real pgvector similarity search. `make test` truncates every
table; run `make reseed` afterward.

## Layout

```
HospitalRAG_DB/
├── docs/
│   ├── 01_requirements.md     Requirements, scope decisions, and a documented limitation
│   ├── 02_er_diagram.md       ERD + the vector-column-is-a-schema-commitment explanation
│   ├── 03_optimization.md     Module 13 -- HNSW EXPLAIN ANALYZE evidence (~33x at 20K rows)
│   ├── 04_interactive_learning.md   Guided tour of the Makefile learning path
│   └── screenshots/           UI walkthrough images + walkthrough.gif
├── sql/01_schema.sql          Relational + vector schema: tables, HNSW index, GIN indexes
├── Makefile                   `make help` -- one target per pipeline step
├── scripts/
│   ├── sample_documents/      6 real (hand-written) hospital documents used for seeding
│   ├── generate_seed_data.py  Ingests the sample documents through the real pipeline
│   ├── eval_dataset.py        Labeled question set for the evaluation harness
│   ├── api_walkthrough.sh     Narrated end-to-end curl script behind `make demo`
│   └── benchmark_vector_index.sh   Reproduces the HNSW benchmark from docs/03_optimization.md
├── Dockerfile / docker-compose.yml   postgres (pgvector image) + backend, model cache volume
├── python/
│   ├── app.py                 FastAPI -- thin HTTP layer over the repositories/services below
│   ├── static/                index.html / style.css / app.js -- chat UI + admin console
│   └── rag/
│       ├── db/connection.py       psycopg3 pool with pgvector type registration
│       ├── repositories/          One per entity; chunk_repository.py holds the vector search
│       ├── services/
│       │   ├── embedding_service.py    Pluggable: local (sentence-transformers) or OpenAI
│       │   ├── chunking_service.py     Token-based sliding window (tiktoken)
│       │   ├── extraction_service.py   PDF/TXT/Markdown extraction + cleaning
│       │   ├── ingestion_service.py    Orchestrates extract -> chunk -> embed -> store
│       │   ├── retriever_service.py    Embed query -> pgvector search -> similarity floor
│       │   ├── prompt_service.py       Builds the grounded, citation-aware prompt
│       │   ├── chat_service.py         Orchestration + the no-hallucination guard
│       │   ├── evaluation_service.py   Module 10: semantic vs. lexical recall/precision
│       │   └── llm/                    Provider abstraction: local (transformers) / OpenAI
│       └── exceptions.py          Domain errors (DuplicateDocumentError, LLMGenerationError, etc.)
└── tests/                     pytest, one file per concern, runs via Docker with a fake LLM
```

## What each failure test proves

| Requirement | Test |
|---|---|
| Duplicate user email | Repository-level `UniqueViolation` -> `DuplicateEmailError` (same pattern as the other two projects) |
| Duplicate document upload | `tests/test_documents.py::test_duplicate_file_upload_rejected` |
| Unsupported file type | `tests/test_documents.py::test_extract_unsupported_type_raises` |
| Empty/unextractable document | `tests/test_documents.py::test_ingest_failure_marks_document_failed` |
| Chunk-level re-ingestion dedup | `tests/test_documents.py::test_chunk_level_dedup_within_same_document` |
| Department-scoped retrieval | `tests/test_retrieval.py::test_retrieve_filters_by_department` |
| No-hallucination guard | `tests/test_chat_service.py::test_ask_without_context_skips_llm_entirely` |
| Conversation memory reaches the prompt | `tests/test_chat_service.py::test_follow_up_question_reuses_conversation_and_injects_history` |
| Evaluation harness scores correctly | `tests/test_evaluation.py::test_evaluation_perfect_recall_when_document_is_relevant` |

## Bugs found and fixed while building this (all caught by actually running it)

- **A bare Python list doesn't adapt to `vector` in a comparison.**
  `embedding <=> [0.1, 0.2, ...]` raised `operator does not exist:
  vector <=> double precision[]` — INSERT tolerates a plain list
  (assignment context allows an implicit cast), but `ORDER BY`/`WHERE`
  comparisons don't. Fixed by wrapping every embedding parameter in
  `pgvector.Vector(...)` before it reaches a query.
  (`python/rag/repositories/chunk_repository.py`)
- **The local LLM answered a general-knowledge question anyway.**
  Asking "what is the capital of France?" with zero relevant documents
  ingested got the answer "Paris" — the system prompt's "say you don't
  know" instruction isn't reliable enough on a small model to be the
  only safeguard. Fixed with a deterministic short-circuit: zero
  retrieved chunks skips the LLM call entirely. See Stage 4 of
  `docs/04_interactive_learning.md` for the full story.
  (`python/rag/services/chat_service.py`)
- **Duplicate-document detection tried to query an aborted
  transaction.** After a `UniqueViolation` on `file_hash`, the
  follow-up "what's the existing document's title" lookup reused the
  same (now-failed) transaction and raised `InFailedSqlTransaction`.
  Fixed by running that lookup in a fresh connection, after the
  original transaction's rollback had actually completed.
  (`python/rag/repositories/document_repository.py`)
- **The citation "[1]" rank showed as empty brackets.** The immediate
  `/api/chat/ask` response returns raw retriever results, which don't
  carry a `rank` field (that's only added once a citation is
  persisted) — the UI now falls back to the array position.
  (`python/static/app.js`)
- **`accelerate` was a missing dependency**, not a bug in the RAG logic
  — `device_map="cpu"` in the transformers pipeline needs it installed;
  without it, the very first chat request 500'd.
- **Deduplication only worked within one document, not across
  uploads.** The original design let an admin upload the exact same
  file twice as two separate documents with duplicate chunks. Added
  `hospital_documents.file_hash` (`UNIQUE`) so a byte-identical
  re-upload is rejected before any extraction work happens.
- **Table bloat skewed an `EXPLAIN` result while building
  `docs/03_optimization.md`.** After deleting 20,000 synthetic
  benchmark rows, a query against the (now 12-row) table still picked
  an index scan — `DELETE` doesn't reclaim pages, so the planner still
  saw a "big" table until `VACUUM FULL` ran. See
  `docs/03_optimization.md` Section 3.

## Key design decisions

- **The vector column's dimension is a schema-time commitment, not a
  config value.** `document_chunks.embedding` is `vector(384)`,
  matching the default local embedding model. Switching
  `EMBEDDING_PROVIDER` after documents are already ingested doesn't
  retroactively fix anything — old chunks keep old vectors, new
  queries use the new provider, and retrieval quality silently
  degrades with no error. OpenAI's embedding models support truncating
  their native output via a `dimensions` parameter (Matryoshka
  representation learning), which is what lets this project offer
  OpenAI embeddings *without* a migration — a real technique, not
  guaranteed to be available for every provider/model combination. See
  `docs/02_er_diagram.md`.
- **A deterministic no-context guard, not just a system prompt
  instruction.** Prompt engineering alone isn't a safety boundary on a
  small model — see "Bugs found and fixed" above.
- **Checkout vs. payment; enrollment vs. grading; here, ingestion vs.
  chat.** Consistent with the other two projects' separation of
  concerns: `IngestionService` (slow, admin-triggered, writes) is
  fully decoupled from `ChatService`/`RetrieverService` (the read/query
  path). Neither blocks on the other.
- **No LangChain/LlamaIndex.** This project's own stated learning
  objectives are to understand embeddings, chunking, and retrieval —
  hand-writing the pipeline serves that goal the same way hand-written
  SQL (instead of an ORM) served the other two projects.
- **Login is demo-mode-permissive**, identical in spirit to
  `mini_EcommerceDB` and `EMS_DB` — any password works, an unrecognized
  email auto-creates an account. Flagged here, not silently dropped
  from what a real system would do.

## Next milestones

- **Query rewriting/condensation** for follow-up questions — see the
  "Known limitation" in `docs/01_requirements.md`.
- **Reranking** (e.g. MMR) after the initial top-K similarity search,
  for retrieval diversity.
- **LLM-as-judge answer-quality evaluation**, alongside the current
  retrieval-only evaluation harness.
- **Word document (.docx) ingestion**, a fourth extraction strategy.
- **True token-level streaming** for the local provider (currently
  simulated — see `LocalLLMProvider.stream()`); the OpenAI provider
  already streams real tokens.
