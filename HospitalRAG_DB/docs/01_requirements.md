# Module 0-1 — Requirement Analysis & Domain Modeling

## Business Problem

Hospitals accumulate thousands of documents — clinical guidelines, SOPs,
patient education material, drug information, insurance policy text,
discharge summary templates. Staff waste time manually searching PDFs
to answer routine questions ("What's the treatment protocol for
dengue?"). This system lets staff ask natural-language questions and
get an answer grounded in the hospital's own documents, with citations
— not the model's general pretrained knowledge.

## Goal

> "What is the treatment protocol for dengue?"

The assistant retrieves the relevant chunks of the hospital's own
documents, builds a prompt that constrains the LLM to answer *from that
context*, and returns an answer with citations back to the source
document. If nothing relevant is retrieved, it says so instead of
guessing.

## Actors

- **Staff** — asks questions in a chat interface, sees prior
  conversations, sees which documents backed each answer.
- **Admin** — uploads/manages documents, manages departments, views the
  audit log and retrieval evaluation reports.

## Functional Requirements

1. A user logs in and asks questions in a persistent conversation
   (multi-turn — a follow-up question should have access to recent
   turns, not just the current one).
2. An admin uploads a document (PDF, TXT, or Markdown); it's extracted,
   cleaned, split into overlapping chunks, embedded, and stored.
   Dedup happens at two layers: uploading the exact same file twice is
   rejected outright (`hospital_documents.file_hash` is `UNIQUE`,
   checked before any extraction work happens), and re-ingesting the
   same document (e.g. a retried/resumed ingestion) skips re-embedding
   any chunk whose content it already stored
   (`UNIQUE(document_id, content_hash)` on `document_chunks`).
3. Asking a question: embed the question, retrieve the top-K most
   similar chunks via pgvector, optionally scoped to a department,
   build a grounded prompt, generate an answer, return it with the
   source documents cited.
4. If retrieval finds nothing relevant (or the document store is
   empty), the assistant says it doesn't know rather than answering
   from general knowledge — this is the actual point of RAG over a
   bare LLM.
5. Every question and answer is logged (audit trail) with which
   document chunks were used, for compliance and for the evaluation
   harness described below.
6. The LLM backend is swappable without touching the retrieval or
   ingestion code: a local, no-API-key model by default, and a
   real OpenAI model if `OPENAI_API_KEY` is configured. See "Scope
   decisions" for why this had to be designed in from the start rather
   than bolted on later.

## Non-Functional Requirements

- Referential integrity at the database level, same as the other two
  projects in this repo.
- The vector index (HNSW via pgvector) is chosen and benchmarked, not
  assumed — see `docs/03_optimization.md`.
- Changing the embedding model is a **migration**, not a config flip:
  vectors from two different embedding models don't live in the same
  space, and pgvector's column dimension is fixed at schema time. This
  is documented explicitly because it's the single easiest mistake to
  make in a real RAG system — see "Key design decisions" in the README.
- Everything runs from `docker compose up`, no API key required, same
  as the other two projects. An API key *upgrades* the answer quality;
  it is never required to see the system work end to end.

## Known limitation: follow-up questions aren't retrieval-rewritten

Conversation history (Module 9) is injected into the **LLM prompt** for
follow-up questions, so the model has it when answering. It is *not*
used to rewrite the follow-up's own text before **retrieval** runs. A
pronoun-heavy follow-up like "what about severe cases?" is embedded and
searched using only those five words — with nothing in them to anchor
the search, retrieval can come back empty even though a human reading
the transcript would immediately understand what's being asked, and the
assistant falls back to "I don't have that information." Caught by
writing `tests/test_chat_service.py`'s follow-up test with a vague
question and watching retrieval silently return nothing.

The real fix is **query rewriting/condensation**: run the follow-up
plus recent history through a small LLM call first, produce a
standalone question ("what about severe cases of dengue?"), and embed
*that* for retrieval. It's a well-known RAG technique and a legitimate
next milestone — not built here because it adds another LLM call (more
latency, another prompt to design and evaluate) to a system that
already prioritized "understand the mechanics" over "handle every
real-world phrasing." Ask follow-ups that still name the topic, the
same way you'd ask a search engine.

## Entities

| Entity | Description |
|---|---|
| Departments | Scopes documents and users (e.g. Cardiology, Pharmacy) |
| Users | Staff/admin; login-capable |
| HospitalDocuments | An uploaded source document (PDF/TXT/MD) |
| DocumentChunks | A chunk of a document, with its embedding vector |
| Conversations | A chat session belonging to a user |
| Messages | One turn (user question or assistant answer) in a conversation |
| MessageCitations | Which document chunks backed a given answer |
| AuditLogs | Who did what, when — questions asked, documents uploaded |

## Scope decisions (v1)

The brief's Module 1/2 entity lists also include full hospital
operational records — Patients, Doctors, Appointments, Medicines,
Prescriptions, Lab Reports. Those belong to a hospital *management*
system (a different, much larger project — closer in shape to the EMS
project than to this one). This build's actual goal is a **document
question-answering assistant**: none of the RAG pipeline (ingestion,
chunking, embedding, retrieval, prompting, generation) touches
clinical records, so seeding fake patient/prescription data would be
pure padding with no bearing on what this project teaches. Departments
are kept (documents and users are scoped by department, which is
enough to demonstrate metadata-filtered retrieval); deep clinical
entities are cut.

Similarly cut for scope, each a real "next milestone" rather than an
oversight:

- **Word document (.docx) ingestion** — PDF, TXT, and Markdown already
  exercise three distinct extraction strategies (binary parsing, plain
  read, lightweight markup cleaning); a fourth format adds a dependency
  without teaching a new lesson.
- **LangChain / LlamaIndex** — deliberately not used. This project's
  stated learning objectives are "understand embeddings, chunking,
  semantic search, prompt engineering" — using a framework that
  abstracts those away would work against the point, the same reason
  the other two projects hand-write SQL instead of using an ORM.
- **Reranking / MMR diversity** — top-K cosine similarity is
  implemented and its limits are documented; a reranking pass is a
  documented next step, not built here.
- **LLM-as-judge evaluation** — the evaluation harness (Module 10)
  measures retrieval precision/recall against a labeled question set,
  which needs no extra LLM calls. Using an LLM to grade answer quality
  is a real technique but adds cost/complexity better suited to a v2.

## Login (consistency with the other two projects)

Login is demo-mode-permissive, same as `mini_EcommerceDB` and
`EMS_DB`: any email/password logs you in, and an unrecognized email
auto-creates an account. This is flagged the same way it was flagged
in those two projects' READMEs — a deliberate learning-sandbox choice,
not something a real hospital system would ever do.
