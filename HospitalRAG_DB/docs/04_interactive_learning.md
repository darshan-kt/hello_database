# Interactive Learning Guide

Same philosophy as the other two projects in this repo: learn by doing,
one `make` command at a time. This project's focus is **RAG** —
embeddings, chunking, vector search, prompt construction, and the
gap between "an LLM that sounds confident" and "an LLM that's actually
grounded in your documents."

Requires: `docker`, `make`, `curl`, `jq`.

Full command reference: `make help`. This document is the guided tour.

**A note on patience**: the default local LLM runs on CPU with no GPU.
The first question asked after a fresh `make up` downloads and loads
the model (budget ~90 seconds); after that, each answer takes roughly
10-15 seconds. This is the honest cost of the "zero API keys, runs
anywhere" default — see the README for how to swap in OpenAI for
speed and quality once you have a key.

---

## Stage 0 — Start the environment and ingest the sample documents

```bash
make up
make seed
```

**What happens:** `docker compose` starts `postgres` (the
`pgvector/pgvector:pg16` image — Postgres with the `vector` extension
pre-installed) and `backend`. Postgres auto-runs `sql/01_schema.sql` on
first boot. `make seed` then runs `scripts/generate_seed_data.py`
*inside* the backend container: it reads 6 real (hand-written, genuinely
informative) hospital documents from `scripts/sample_documents/` and
pushes each one through the *actual* ingestion pipeline — extract, chunk,
embed, store — the same code path a real upload takes.

**Concept:** why seeding calls the real `IngestionService` instead of
just inserting rows — this exercises the embedding model and the
chunker as a side effect of seeding, so if either is broken, seeding
fails loudly instead of leaving you to discover it later.

---

## Stage 1 — Look at the schema before asking anything

```bash
make db-tables
make db-describe TABLE=document_chunks
make db-shell        # then: SELECT title, status FROM hospital_documents;
```

**What to notice:** `document_chunks.embedding` is `vector(384)` — a
pgvector column, not a generic array. `make db-describe TABLE=document_chunks`
also shows `idx_chunks_embedding_hnsw` (the approximate-nearest-neighbor
index that makes similarity search fast) and `search_vector` (a
generated `tsvector` column, the lexical-search fallback used by the
evaluation harness in Stage 5).

---

## Stage 2 — Walk the question-answering pipeline, one call at a time

Your session persists via a cookie file (`.staff_cookies.txt`).

| # | Command | HTTP call | Concept |
|---|---------|-----------|---------|
| 1 | `make login` | `POST /api/auth/login` | Demo-mode auth (any password works) — same as the other two projects |
| 2 | `make departments` | `GET /api/departments` | Plain read; departments scope documents and (optionally) retrieval |
| 3 | `make ask Q="What is the treatment protocol for dengue fever?"` | `POST /api/chat/ask` | **The whole pipeline**: embed the question -> pgvector cosine similarity search -> build a grounded prompt -> generate -> store the answer + citations |
| 4 | `make ask Q="What is the capital of France?"` | same endpoint | Retrieval finds nothing above the similarity floor -> **the LLM is never called** (see Stage 4) |
| — | `make ask Q="What about severe dengue cases?" CONVERSATION=<id>` | same endpoint | Follow-up in the same conversation — history reaches the *prompt*, but not the *retrieval query* (a documented limitation, see Stage 4) |
| 5 | `make my-conversations` | `GET /api/conversations` | Each conversation you've had |
| — | `make conversation-messages CONVERSATION=<id>` | `GET /api/conversations/<id>/messages` | Full transcript with citations per answer |

Run `make demo` once to see all of this (plus the admin side) happen
automatically and narrated, *then* come back and run individual
targets against the data it left behind.

---

## Stage 3 — The admin side: ingestion, from the terminal

```bash
make admin-login
make upload FILE=scripts/sample_documents/hand_hygiene_sop.md DEPARTMENT=4
make upload FILE=scripts/sample_documents/hand_hygiene_sop.md DEPARTMENT=4   # run it again
make documents
make document-chunks DOCUMENT=<id>
```

**Concept — two layers of dedup:** the second identical upload is
rejected outright (`409 DuplicateDocumentError`) before any extraction
work happens — `hospital_documents.file_hash` is `UNIQUE`. This was a
real bug while building this project: the first version only deduped
*within* a document's own chunks (for a retried ingestion), so
uploading the same file twice silently created two documents with
identical content. See the README's "Bugs found and fixed" section.

**Try it:** `make document-chunks DOCUMENT=1` and compare the `content`
of each chunk against `scripts/sample_documents/dengue_treatment_protocol.md`
— you're looking at the actual token-based sliding-window split
(400 tokens, 50 overlap) that ran at ingestion time.

---

## Stage 4 — Why "I don't know" beats a hallucinated answer

This is the actual point of RAG, and the part worth understanding
slowly.

```bash
make ask Q="What is the capital of France?"
```

The system prompt (`python/rag/services/prompt_service.py`) already
tells the model "if the context doesn't contain the answer, say you
don't know." **That instruction alone was not enough.** While building
this project, asking an out-of-scope question against the small local
model got the answer "Paris" anyway — a small model's instruction
-following isn't reliable enough to be the only thing standing between
your users and a hallucination. The actual fix, in
`python/rag/services/chat_service.py`: when retrieval returns zero
chunks above the similarity floor, **the LLM is never called at all** —
a fixed, deterministic response is returned instead. Prompt
engineering is not a safety boundary; application logic is.

The flip side — a related, *undocumented-until-you-hit-it* limitation —
is in `docs/01_requirements.md`'s "Known limitation" section: a
follow-up question like "what about severe cases?" is embedded and
searched using *only those words*, not the conversation history. Try
it:

```bash
make ask Q="What is the treatment for dengue?"                          # works
make ask Q="What about severe cases?" CONVERSATION=<id-from-above>      # may retrieve nothing
make ask Q="What about severe dengue cases?" CONVERSATION=<id-from-above>  # names the topic -- works
```

---

## Stage 5 — The vector index, benchmarked for real

```bash
make explain                    # at the real seeded scale (12 chunks) -- planner ignores the index, correctly
make benchmark-vector-index     # inserts 20,000 synthetic vectors, compares with/without HNSW, cleans up after itself
```

Real numbers from this exact benchmark: **0.49ms with the HNSW index,
16.1ms without it** at 20,012 rows — about 33x. Full writeup, plus a
bonus finding about `VACUUM` and table bloat that the benchmark itself
surfaced, in `docs/03_optimization.md`.

**Concept:** an index that's *correctly* unused at demo scale (12 rows)
doesn't mean the index is pointless — it means you're not at the scale
where it matters yet. This is the same lesson `EMS_DB` teaches with
`courses`, from a different angle: know the difference between "this
index isn't earning its keep right now" and "this index is broken."

---

## Stage 6 — Run the evaluation harness

```bash
make run-evaluation
```

Scores semantic (vector) retrieval against a hand-labeled question set
(`scripts/eval_dataset.py`) — and, on the same questions, plain keyword
search over the same chunks. Read the per-question `lexical_recall`
column: several questions score 0% lexically ("What is the antidote for
acetaminophen overdose?" against a document that happens to phrase it
differently) while scoring 100% semantically. That gap *is* the reason
to build a vector search pipeline instead of `LIKE '%query%'`.

---

## Stage 7 — See it all happen automatically

```bash
make demo
```

Runs Stages 2-4 end to end (plus an admin upload + dedup + evaluation
run), narrated. Read `scripts/api_walkthrough.sh` alongside the output.

## Stage 8 — Verify your understanding against the test suite

```bash
make test
```

23 tests. Notice `tests/conftest.py`'s `FakeLLMProvider` — the
automated suite never makes a real (slow) model call; it injects a fake
provider into `ChatService` so retrieval, prompting, citation storage,
and the no-context guard are all tested at full speed and
deterministically, while the *real* local model is exercised manually
(Stage 2) and in `make demo`. `make test` truncates every table; run
`make reseed` afterward.

---

## Cheat sheet

```
make up && make seed          start everything, ingest the demo documents
make demo                      watch the full lifecycle, narrated (real LLM call)
make db-shell                   poke at chunks/embeddings yourself
make explain / benchmark-vector-index   the vector-index story, small scale and real scale

make login                      STEP 1
make ask Q="..."                STEP 3 -- the whole pipeline in one call
make my-conversations / conversation-messages CONVERSATION=<id>

make admin-login
make upload FILE=... DEPARTMENT=...    STEP 5 -- ingest a document
make documents / document-chunks DOCUMENT=<id>
make run-evaluation               STEP 6 -- semantic vs. lexical recall

make test                       run the automated tests (truncates tables, uses a fake LLM)
make reseed                      put the demo documents back
make reset                       nuke everything, including cached models, and start over
```
