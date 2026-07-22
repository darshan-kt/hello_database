# hello_database

My hands-on database learning journal. The goal isn't to read about
databases — it's to build real, working, production-style backend
systems end to end until relational modeling, SQL, and backend
architecture stop being abstract and start being muscle memory.

Each project in this repo is a step up in difficulty from the last, and
each one is fully Dockerized with a Makefile you can use to learn it
interactively, one command at a time.

## Objective

Go from "I know what a database is" to "I can design, build, optimize,
and explain a real backend system" — by actually shipping one, not just
reading a chapter on normalization. Every project here follows the same
professional workflow: requirements → domain modeling → ER diagram →
normalized schema → seed data → a layered Python backend → the business
logic that makes a database project *hard* (transactions, concurrency,
constraints) → a web UI to see it work → tests for the failure modes →
`EXPLAIN`-backed optimization notes.

## The learning curve so far

```
docs/1.Database_Basics_Reference.md
   Relational vs NoSQL vs Vector DBs -- what each is for, when to
   reach for which. Theory foundation before writing any code.
        │
        ▼
mini_EcommerceDB/  (MySQL)
   Core relational modeling: normalization, foreign keys, CHECK
   constraints, ACID transactions, row-level locking to prevent
   overselling stock, the repository pattern.
        │
        ▼
EMS_DB/  (PostgreSQL)
   Leveled up to advanced SQL: CTEs, window functions, recursive
   queries, materialized views, JSONB, full-text search -- plus a
   two-role system (student/admin) and a richer domain (12 tables,
   3 views, 1 materialized view).
        │
        ▼
(next) RAG project  (Vector DB)
   Embeddings + semantic search -- the "Vector DB" branch from the
   basics doc, built out for real.
```

---

## Project 1 — Mini E-Commerce Backend

**Stack:** MySQL 8 · Python (Flask, repository + service pattern) · Docker

![Mini E-Commerce walkthrough: register, browse, add to cart, checkout, pay, order history](mini_EcommerceDB/docs/screenshots/walkthrough.gif)

Register → browse a catalog → cart → checkout → pay → order history.
The point of this project was the fundamentals: a normalized schema,
foreign keys and `UNIQUE`/`CHECK` constraints doing real enforcement
work, and a checkout flow that's genuinely transactional — `SELECT ...
FOR UPDATE` row locks so two customers can't both buy the last unit of
stock, with tests proving the whole thing rolls back cleanly when it
should.

**[→ mini_EcommerceDB/README.md](mini_EcommerceDB/README.md)** — Docker
quickstart, the web UI, and `make demo` for a narrated walkthrough of
every step from the terminal.

---

## Project 2 — Education Management System (EMS)

**Stack:** PostgreSQL 16 · Python (Flask, psycopg3) · Docker

![EMS walkthrough: student enrolls, admin grades, GPA rankings, department hierarchy, materialized view, JSONB](EMS_DB/docs/screenshots/walkthrough.gif)

A university backend: departments (with a real self-referential
hierarchy), courses with prerequisite chains, enrollment with
seat-locking, attendance, grading, fee payments gating certificate
issuance. This project's actual purpose was **advanced PostgreSQL**:
CTEs for reporting rollups, window functions for GPA rankings,
recursive CTEs for the department tree and prerequisite chains, a
materialized view refreshed on demand, JSONB for flexible assignment
settings, and full-text search over courses/teachers/students.

**[→ EMS_DB/README.md](EMS_DB/README.md)** — Docker quickstart, the
student portal + admin console, and `make demo` for a narrated
walkthrough touching every one of those PostgreSQL features.

---

## What's next — a RAG project (Vector DB)

The basics doc I started with already sketches the vector-database
branch of the database tree — Pinecone, Milvus, Weaviate, Qdrant,
Chroma — for embeddings and similarity search. The next project builds
that out for real: a Retrieval-Augmented Generation backend, storing
document embeddings in a vector store, doing semantic search over them,
and feeding the results into an LLM — most likely paired with a
relational database for the metadata/document bookkeeping a pure vector
store isn't good at, the same way the two projects above paired a
relational schema with the business logic around it.

## Repo layout

```
hello_database/
├── docs/
│   ├── 1.Database_Basics_Reference.md          Relational vs NoSQL vs Vector DBs
│   ├── 2.Mini_Ecommerce_Database_Project_Guide.md   The brief behind mini_EcommerceDB/
│   └── 3.EMS_DB                                 The brief behind EMS_DB/
├── mini_EcommerceDB/     Project 1 -- MySQL, transactions, the fundamentals
└── EMS_DB/               Project 2 -- PostgreSQL, advanced SQL, reporting
```
