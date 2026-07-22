# Module 13 — Indexing & Query Optimization

Every plan below is a real `EXPLAIN ANALYZE` run against this project's
database. The vector-index evidence needed a corpus larger than the 6
seeded sample documents provide (12 chunks) to show a genuine
difference, so it was captured against a temporary batch of 20,000
synthetic vectors inserted, benchmarked, and deleted for this doc — see
the commands below if you want to reproduce it yourself.

## 1. The HNSW index: why the vector column has one at all

```sql
EXPLAIN ANALYZE
SELECT chunk_id, 1 - (embedding <=> $1) AS similarity
FROM document_chunks
ORDER BY embedding <=> $1
LIMIT 5;
```

**With `idx_chunks_embedding_hnsw` (20,012 rows):**

```
Limit (actual time=0.424..0.427 rows=5 loops=1)
  ->  Index Scan using idx_chunks_embedding_hnsw on document_chunks
        (cost=522.49..38256.30 rows=20012 width=24) (actual time=0.423..0.425 rows=5 loops=1)
        Order By: (embedding <=> $1)
Execution Time: 0.487 ms
```

**Same query, index dropped:**

```
Limit (actual time=15.621..15.624 rows=5 loops=1)
  ->  Sort (actual time=15.620..15.621 rows=5 loops=1)
        Sort Key: ((document_chunks.embedding <=> $1))
        Sort Method: top-N heapsort  Memory: 25kB
        ->  Seq Scan on document_chunks (actual time=0.048..13.700 rows=20012 loops=1)
Execution Time: 16.101 ms
```

**~33x** at 20K rows. Without the index, every similarity search is a
full table scan plus a sort — `ORDER BY embedding <=> $1 LIMIT 5` still
has to compute the distance for *every* row before it can know which 5
are closest. HNSW (Hierarchical Navigable Small World) trades exactness
for speed: it's an *approximate* nearest-neighbor index, so at extreme
scale it can occasionally miss the true nearest match in exchange for
sublinear search time. For a document-QA assistant retrieving top-5
context chunks, an approximate top-5 that's right 99%+ of the time is
the correct trade — a single missed chunk out of 5 candidates rarely
changes the answer, and losing that trade would mean scanning the whole
table on every question asked, on every user's every message.

To reproduce this yourself: `make db-shell`, then see
`docs/04_interactive_learning.md`'s benchmark commands.

## 2. Small tables still don't use their indexes (same lesson as the other two projects)

At this project's actual seeded scale (12 real chunks), the exact same
`document_id` lookup that benefits from an index at 20K rows doesn't
use one:

```sql
EXPLAIN ANALYZE SELECT * FROM document_chunks WHERE document_id = 1;
```

```
Seq Scan on document_chunks (cost=0.00..3.15 rows=2 width=1330) (actual time=0.008..0.014 rows=2 loops=1)
  Filter: (document_id = 1)
  Rows Removed by Filter: 10
Execution Time: 0.053 ms
```

Correct, not a bug — see `EMS_DB/docs/03_optimization.md` for the same
finding on that project's `courses` table. An unused index on a small
table is not something to fix.

## 3. A bonus lesson this project surfaced: `VACUUM` matters too

Capturing the evidence above required inserting 20,000 synthetic rows
and then deleting them again. Right after that delete, the *exact same*
`document_id` lookup from Section 2 was still picking an index scan,
even though the table was back down to 12 real rows:

```
Bitmap Heap Scan on document_chunks (cost=16.28..24.18 rows=2 width=1330) (actual time=0.021..0.021 rows=2 loops=1)
  ->  Bitmap Index Scan on idx_chunks_document (actual time=0.018..0.019 rows=2 loops=1)
```

`DELETE` doesn't reclaim disk pages -- it just marks rows dead. The
table's on-disk size (and the row-estimate the planner uses) doesn't
shrink until a vacuum runs, so a table that briefly held 20K rows and
shrank back down can still look "big" to the planner afterward. Running
`VACUUM FULL document_chunks; ANALYZE document_chunks;` reclaimed the
space, and the plan went back to the expected sequential scan (Section
2's output). This is the same family of issue as `EMS_DB`'s "run
`ANALYZE` after a bulk load" finding, from the opposite direction: bulk
*deletes*, not bulk *inserts*, also leave the planner with a stale
picture until you tell it to look again. `autovacuum` handles this
automatically in the background in a real deployment; it's worth
knowing what it's for the day you're staring at a confusing plan on a
table that "should" be small.

## 4. JSONB: `audit_logs.detail`

Same story as Section 2 -- `audit_logs` is small at this project's demo
scale, so the planner correctly ignores `idx_audit_logs_detail` (GIN)
and scans instead:

```sql
EXPLAIN ANALYZE SELECT * FROM audit_logs WHERE detail @> '{"chunks_retrieved": 0}';
-- Seq Scan on audit_logs ... Execution Time: 0.024 ms
```

Forcing it off to confirm the index itself is wired correctly (the same
technique used in `EMS_DB`'s optimization doc):

```sql
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT * FROM audit_logs WHERE detail @> '{"chunks_retrieved": 0}';
```

```
Bitmap Heap Scan on audit_logs (cost=12.98..16.99 rows=1 width=174) (actual time=0.009..0.010 rows=0 loops=1)
  ->  Bitmap Index Scan on idx_audit_logs_detail (actual time=0.004..0.004 rows=0 loops=1)
        Index Cond: (detail @> '{"chunks_retrieved": 0}'::jsonb)
Execution Time: 0.047 ms
```

Not the focus of this project's optimization story (that's the vector
index) -- included because the pattern ("prove the plan you'd get at
real scale, since small-scale won't show it") is worth reinforcing a
third time across this repo's three projects until it's automatic.

## General index rules applied in this schema

- Every foreign key has a supporting B-tree index.
- The vector column gets an HNSW index specifically because it's the
  *only* column ever searched by similarity rather than equality --
  B-tree indexes cannot accelerate a `<=>` comparison at all.
- `idx_chunks_search` (GIN, full-text) exists for the evaluation
  harness's semantic-vs-lexical comparison (Module 10), not for the
  main retrieval path.
- No index was added speculatively -- each one maps to a real query in
  `python/rag/repositories/`.
