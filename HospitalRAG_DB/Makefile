# ============================================================================
# Hospital AI Knowledge Assistant -- Interactive Learning Makefile
#
# Run `make` or `make help` to see every step. Each target prints the HTTP
# call and the RAG-pipeline concept happening underneath it -- embedding,
# chunking, vector search, prompt construction, generation -- one command
# at a time.
#
# See docs/04_interactive_learning.md for the full guided tour.
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Overridable variables -------------------------------------------
BASE_URL      ?= http://localhost:5002
STAFF_JAR     ?= .staff_cookies.txt
ADMIN_JAR     ?= .admin_cookies.txt
NAME          ?= Demo Learner
EMAIL         ?= demo.learner@hospital.test
PASSWORD      ?= learn-123
Q             ?= What is the treatment protocol for dengue fever?
CONVERSATION  ?=
DEPARTMENT    ?=
FILE          ?= scripts/sample_documents/dengue_treatment_protocol.md
DOCUMENT      ?=
DEPT_NAME     ?= Radiology
DEPT_CODE     ?= RADIOLOGY
TABLE         ?= document_chunks

PRETTY = jq . 2>/dev/null || cat

.PHONY: help up down reset logs status seed reseed test clean open-ui \
        db-shell db-tables db-describe explain benchmark-vector-index \
        login me logout departments ask my-conversations conversation-messages \
        admin-login upload documents document-chunks delete-document \
        create-department run-evaluation audit-log demo

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; \
	  printf "\nHospital AI Knowledge Assistant -- Interactive Learning Makefile\n"; \
	  printf "==================================================================\n"} \
	  /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Suggested first run:"
	@echo "  make up            # start Postgres+pgvector and the backend"
	@echo "  make seed          # ingest 6 real sample hospital documents"
	@echo "  make demo          # watch the full lifecycle happen, narrated (includes a real LLM call -- be patient)"
	@echo ""
	@echo "Full guided tour: docs/04_interactive_learning.md"
	@echo ""

##@ Infrastructure

up: ## Start Postgres+pgvector and the backend (builds the image on first run)
	@echo "==> docker compose up -d --build"
	docker compose up -d --build
	@echo "==> Waiting for both containers to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' rag_postgres 2>/dev/null)" = "healthy" ] && \
	       [ "$$(docker inspect -f '{{.State.Health.Status}}' rag_backend 2>/dev/null)" = "healthy" ]; do \
	  sleep 2; \
	done
	@echo "==> Ready.  UI: $(BASE_URL)   Postgres: localhost:5434 (user=rag_app pass=rag_app_pw)"
	@echo "    The local embedding model downloads on first seed; the local LLM downloads on first question asked."

down: ## Stop containers (keeps the database + model cache volumes)
	docker compose down

reset: ## Full reset: wipe DB + model cache volumes, rebuild, restart, reseed
	@echo "==> Wiping containers + volumes for a clean slate (this re-downloads the models)..."
	docker compose down -v
	$(MAKE) --no-print-directory up
	$(MAKE) --no-print-directory seed
	rm -f $(STAFF_JAR) $(ADMIN_JAR)

logs: ## Follow the backend's logs
	docker compose logs -f backend

status: ## Show container status
	docker compose ps

seed: ## Ingest the 6 sample hospital documents (skips if already seeded)
	@echo "==> Ingesting sample documents (extract -> chunk -> embed -> store)..."
	docker compose run --rm backend python scripts/generate_seed_data.py

reseed: ## Force-wipe and re-ingest the demo dataset (use after `make test`, which truncates every table)
	@echo "==> Force-reseeding..."
	docker compose run --rm backend python scripts/generate_seed_data.py --force

test: ## Run the pytest suite inside Docker (WARNING: truncates all tables; uses a fake LLM, so it's fast)
	@echo "==> Running tests inside the backend container against the real Postgres+pgvector."
	docker compose run --rm backend pytest -v

clean: ## Stop containers, delete all volumes, forget local session cookies
	docker compose down -v
	rm -f $(STAFF_JAR) $(ADMIN_JAR)

open-ui: ## Open the web UI in your default browser
	@command -v xdg-open >/dev/null 2>&1 && xdg-open $(BASE_URL) || \
	 command -v open >/dev/null 2>&1 && open $(BASE_URL) || \
	 echo "Open $(BASE_URL) manually."

##@ Explore the database directly

db-shell: ## Open an interactive psql shell inside the container
	@echo "==> Try: \\dt   SELECT * FROM document_chunks LIMIT 3;   SELECT title, status FROM hospital_documents;"
	docker exec -it rag_postgres psql -U rag_app -d hospital_rag

db-tables: ## List every table in the schema
	docker exec rag_postgres psql -U rag_app -d hospital_rag -c "\dt"

db-describe: ## Show a table's columns, types, keys. Vars: TABLE (default: document_chunks)
	docker exec rag_postgres psql -U rag_app -d hospital_rag -c "\d $(TABLE)"

explain: ## Run EXPLAIN ANALYZE at the real seeded scale (see docs/03_optimization.md for the full-scale comparison)
	@echo "==> Small real corpus (12 chunks): planner correctly prefers a sequential scan"
	@docker exec rag_postgres psql -U rag_app -d hospital_rag -c \
	  "EXPLAIN ANALYZE SELECT * FROM document_chunks WHERE document_id = 1;"
	@echo ""
	@echo "==> For the HNSW index actually winning at scale, run: make benchmark-vector-index"

benchmark-vector-index: ## Reproduce docs/03_optimization.md's HNSW benchmark: insert 20K synthetic vectors, compare with/without the index, clean up
	@bash scripts/benchmark_vector_index.sh

##@ Step by step: Staff (chat)

login: ## STEP 1 -- Log in (demo mode: any email/password works, account auto-created if new). Vars: EMAIL, PASSWORD
	@echo "==> POST /api/auth/login   ->   auto-creates the account if the email isn't found; password isn't checked"
	@curl -sS -c $(STAFF_JAR) -b $(STAFF_JAR) -X POST $(BASE_URL)/api/auth/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"$(EMAIL)","password":"$(PASSWORD)"}' | $(PRETTY)

me: ## Show who you're logged in as (staff session)
	@curl -sS -b $(STAFF_JAR) $(BASE_URL)/api/auth/me | $(PRETTY)

logout: ## Clear the staff session
	@curl -sS -c $(STAFF_JAR) -b $(STAFF_JAR) -X POST $(BASE_URL)/api/auth/logout | $(PRETTY)

departments: ## STEP 2 -- List departments
	@curl -sS $(BASE_URL)/api/departments | $(PRETTY)

ask: ## STEP 3 -- Ask a question (the whole RAG pipeline in one call). Vars: Q, CONVERSATION (id, optional), DEPARTMENT (id, optional)
	@echo "==> POST /api/chat/ask   ->   embed -> pgvector similarity search -> grounded prompt -> LLM generate -> store + cite"
	@echo "    First call on a fresh container downloads+loads the local model (~90s). Warm calls: ~10-15s. Be patient."
	@conv=""; if [ -n "$(CONVERSATION)" ]; then conv=",\"conversation_id\":$(CONVERSATION)"; fi; \
	dept=""; if [ -n "$(DEPARTMENT)" ]; then dept=",\"department_id\":$(DEPARTMENT)"; fi; \
	curl -sS -b $(STAFF_JAR) -X POST $(BASE_URL)/api/chat/ask --max-time 180 \
	  -H 'Content-Type: application/json' \
	  -d "{\"question\":\"$(Q)\"$$conv$$dept}" | $(PRETTY)

my-conversations: ## STEP 4 -- List your conversations
	@curl -sS -b $(STAFF_JAR) $(BASE_URL)/api/conversations | $(PRETTY)

conversation-messages: ## View one conversation's full message history + citations. Vars: CONVERSATION (id, required)
	@if [ -z "$(CONVERSATION)" ]; then echo "Usage: make conversation-messages CONVERSATION=<id>"; exit 1; fi
	@curl -sS -b $(STAFF_JAR) $(BASE_URL)/api/conversations/$(CONVERSATION)/messages | $(PRETTY)

##@ Step by step: Admin

admin-login: ## Log in as admin (demo mode: any email/password works; defaults to the seeded admin@hospital.test)
	@echo "==> POST /api/auth/login"
	@curl -sS -c $(ADMIN_JAR) -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/auth/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"admin@hospital.test","password":"admin-123"}' | $(PRETTY)

upload: ## STEP 5 -- Upload + ingest a document. Vars: FILE (path, required), DEPARTMENT (id, optional)
	@echo "==> POST /api/documents (multipart)   ->   extract -> chunk -> embed -> store; file-hash dedup on re-upload"
	@dept_arg=""; if [ -n "$(DEPARTMENT)" ]; then dept_arg="-F department_id=$(DEPARTMENT)"; fi; \
	curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/documents \
	  -F "file=@$(FILE)" $$dept_arg --max-time 60 | $(PRETTY)

documents: ## List all documents with ingestion status
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/documents | $(PRETTY)

document-chunks: ## View how a document got chunked. Vars: DOCUMENT (id, required)
	@if [ -z "$(DOCUMENT)" ]; then echo "Usage: make document-chunks DOCUMENT=<id>"; exit 1; fi
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/documents/$(DOCUMENT)/chunks | $(PRETTY)

delete-document: ## Delete a document (cascades to its chunks). Vars: DOCUMENT (id, required)
	@if [ -z "$(DOCUMENT)" ]; then echo "Usage: make delete-document DOCUMENT=<id>"; exit 1; fi
	@curl -sS -b $(ADMIN_JAR) -X DELETE $(BASE_URL)/api/documents/$(DOCUMENT) | $(PRETTY)

create-department: ## Add a department. Vars: DEPT_NAME, DEPT_CODE
	@curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/departments \
	  -H 'Content-Type: application/json' \
	  -d '{"name":"$(DEPT_NAME)","code":"$(DEPT_CODE)"}' | $(PRETTY)

run-evaluation: ## STEP 6 -- Run the Module 10 evaluation harness (semantic vs. lexical recall/precision)
	@echo "==> GET /api/evaluation/run   ->   scores retrieval against scripts/eval_dataset.py"
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/evaluation/run --max-time 30 | $(PRETTY)

audit-log: ## View the audit trail (who asked/uploaded what, when)
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/audit | $(PRETTY)

##@ All-in-one

demo: ## Run the entire lifecycle above in one narrated command (safe to re-run; includes a real LLM call)
	@BASE_URL=$(BASE_URL) STAFF_JAR=$(STAFF_JAR) ADMIN_JAR=$(ADMIN_JAR) bash scripts/api_walkthrough.sh
