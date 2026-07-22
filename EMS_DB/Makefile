# ============================================================================
# Education Management System -- Interactive Learning Makefile
#
# Run `make` or `make help` to see every step. Each target prints the HTTP
# call and the SQL/transaction/PostgreSQL-feature happening underneath it
# before running it -- CTEs, window functions, recursive CTEs, materialized
# views, JSONB, full-text search, all reachable as one command each.
#
# See docs/04_interactive_learning.md for the full guided tour.
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Overridable variables (e.g. `make courses DEPARTMENT=2`) ------------
BASE_URL      ?= http://localhost:5001
STUDENT_JAR   ?= .student_cookies.txt
ADMIN_JAR     ?= .admin_cookies.txt
NAME          ?= Demo Learner
EMAIL         ?= demo.learner@ems.test
PASSWORD      ?= learn-123
DEPARTMENT    ?=
COURSE        ?= 1
SEMESTER      ?=
ENROLLMENT    ?=
PAYMENT       ?=
EXAM          ?=
STUDENT       ?=
MARKS         ?= 80
METHOD        ?= card
STATUS        ?= present
SESSION_DATE  ?= $(shell date +%F)
Q             ?=
TYPE          ?= teachers
CERT_TYPE     ?= transcript
DUE_DATE      ?= 2025-11-15
TABLE         ?= courses

PRETTY = jq . 2>/dev/null || cat

.PHONY: help up down reset logs status seed reseed test clean open-ui \
        db-shell db-tables db-describe explain \
        register login me logout departments department-hierarchy \
        courses course-search course-prereqs semesters enroll \
        my-enrollments my-attendance my-grades my-payments pay certificate my-certificates \
        admin-login admin-me record-attendance record-exam-result compute-grade \
        create-invoice directory-search \
        report-departments report-gpa report-toppers report-semesters report-refresh \
        dashboard-admin jsonb-late-penalty jsonb-due-before demo

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; \
	  printf "\nEducation Management System -- Interactive Learning Makefile\n"; \
	  printf "===============================================================\n"} \
	  /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Suggested first run:"
	@echo "  make up            # start Postgres + backend"
	@echo "  make seed          # load the realistic demo dataset"
	@echo "  make demo          # watch the full lifecycle happen, narrated"
	@echo "  make db-shell      # then go look at the rows it created yourself"
	@echo ""
	@echo "Full guided tour: docs/04_interactive_learning.md"
	@echo ""

##@ Infrastructure

up: ## Start Postgres + the backend (builds the image on first run)
	@echo "==> docker compose up -d --build"
	docker compose up -d --build
	@echo "==> Waiting for both containers to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' ems_postgres 2>/dev/null)" = "healthy" ] && \
	       [ "$$(docker inspect -f '{{.State.Health.Status}}' ems_backend 2>/dev/null)" = "healthy" ]; do \
	  sleep 2; \
	done
	@echo "==> Ready.  UI: $(BASE_URL)   Postgres: localhost:5433 (user=ems_app pass=ems_app_pw)"

down: ## Stop containers (keeps the database volume)
	docker compose down

reset: ## Full reset: wipe the DB volume, rebuild, restart, and reseed from scratch
	@echo "==> Wiping containers + database volume for a clean slate..."
	docker compose down -v
	$(MAKE) --no-print-directory up
	$(MAKE) --no-print-directory seed
	rm -f $(STUDENT_JAR) $(ADMIN_JAR)

logs: ## Follow the backend's logs
	docker compose logs -f backend

status: ## Show container status
	docker compose ps

seed: ## Load the realistic demo dataset (skips if already seeded)
	@echo "==> Generating seed data (departments, courses, students, grades, ...)..."
	docker compose run --rm backend python scripts/generate_seed_data.py

reseed: ## Force-wipe and regenerate the demo dataset (use after `make test`, which leaves stray rows)
	@echo "==> Force-reseeding..."
	docker compose run --rm backend python scripts/generate_seed_data.py --force

test: ## Run the pytest suite inside Docker against the real Postgres (WARNING: truncates all tables)
	@echo "==> Running tests inside the backend container. Note: this truncates every table first."
	docker compose run --rm backend pytest -v

clean: ## Stop containers, delete the DB volume, and forget local session cookies
	docker compose down -v
	rm -f $(STUDENT_JAR) $(ADMIN_JAR)

open-ui: ## Open the web UI in your default browser
	@command -v xdg-open >/dev/null 2>&1 && xdg-open $(BASE_URL) || \
	 command -v open >/dev/null 2>&1 && open $(BASE_URL) || \
	 echo "Open $(BASE_URL) manually."

##@ Explore the database directly (see what the API is doing underneath)

db-shell: ## Open an interactive psql shell inside the container
	@echo "==> Try: \\dt   \\dv   \\dm   SELECT * FROM student_dashboard_view LIMIT 5;"
	docker exec -it ems_postgres psql -U ems_app -d ems

db-tables: ## List every table, view, and materialized view in the schema
	docker exec ems_postgres psql -U ems_app -d ems -c "\dt" -c "\dv" -c "\dm"

db-describe: ## Show a table's columns, types, keys. Vars: TABLE (default: courses)
	docker exec ems_postgres psql -U ems_app -d ems -c "\d $(TABLE)"

explain: ## Run EXPLAIN ANALYZE on the key query patterns from docs/03_optimization.md
	@echo "==> Small table (40 rows): planner prefers a sequential scan over the department index"
	@docker exec ems_postgres psql -U ems_app -d ems -c \
	  "EXPLAIN ANALYZE SELECT * FROM courses WHERE department_id = 2;"
	@echo ""
	@echo "==> Larger table (7,956 rows): the attendance index earns its keep"
	@docker exec ems_postgres psql -U ems_app -d ems -c \
	  "EXPLAIN ANALYZE SELECT * FROM attendance WHERE enrollment_id = 100;"
	@echo ""
	@echo "==> Materialized view read (near-instant)..."
	@docker exec ems_postgres psql -U ems_app -d ems -c \
	  "EXPLAIN ANALYZE SELECT * FROM semester_report_mv;"

##@ Step by step: Student (each target = one HTTP call; session persists in $(STUDENT_JAR))

register: ## STEP 1 -- Register a student. Vars: NAME, EMAIL, PASSWORD, DEPARTMENT (id, default: first CS dept)
	@echo "==> POST /api/auth/student/register   ->   INSERT INTO students (...)   [DuplicateEmailError -> 409 if taken]"
	@dept=$(DEPARTMENT); \
	if [ -z "$$dept" ]; then dept=$$(curl -sS $(BASE_URL)/api/departments | jq -r '[.[]|select(.code=="CS")][0].department_id'); fi; \
	curl -sS -c $(STUDENT_JAR) -b $(STUDENT_JAR) -X POST $(BASE_URL)/api/auth/student/register \
	  -H 'Content-Type: application/json' \
	  -d "{\"name\":\"$(NAME)\",\"email\":\"$(EMAIL)\",\"password\":\"$(PASSWORD)\",\"department_id\":$$dept}" | $(PRETTY)

login: ## STEP 1b -- Log in as a student instead (demo mode: any email/password works, account auto-created if new). Vars: EMAIL, PASSWORD
	@echo "==> POST /api/auth/student/login   ->   auto-creates the student if the email isn't found; password isn't checked"
	@curl -sS -c $(STUDENT_JAR) -b $(STUDENT_JAR) -X POST $(BASE_URL)/api/auth/student/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"demo.student@ems.test","password":"learn-123"}' | $(PRETTY)

me: ## Show who you're logged in as (student session)
	@curl -sS -b $(STUDENT_JAR) $(BASE_URL)/api/auth/me | $(PRETTY)

logout: ## Clear the student session
	@curl -sS -c $(STUDENT_JAR) -b $(STUDENT_JAR) -X POST $(BASE_URL)/api/auth/logout | $(PRETTY)

departments: ## STEP 2 -- List departments
	@echo "==> GET /api/departments   ->   SELECT * FROM departments"
	@curl -sS $(BASE_URL)/api/departments | $(PRETTY)

department-hierarchy: ## List departments as a tree (recursive CTE)
	@echo "==> GET /api/departments/hierarchy   ->   WITH RECURSIVE dept_tree AS (...)"
	@curl -sS $(BASE_URL)/api/departments/hierarchy | $(PRETTY)

courses: ## STEP 3 -- Browse courses, optionally filtered. Vars: DEPARTMENT (id)
	@echo "==> GET /api/courses$(if $(DEPARTMENT),?department_id=$(DEPARTMENT),)"
	@curl -sS "$(BASE_URL)/api/courses$(if $(DEPARTMENT),?department_id=$(DEPARTMENT),)" | $(PRETTY)

course-search: ## Full-text search courses. Vars: Q (query)
	@echo "==> GET /api/courses/search?q=$(Q)   ->   WHERE search_vector @@ plainto_tsquery(...)"
	@curl -sS "$(BASE_URL)/api/courses/search?q=$(Q)" | $(PRETTY)

course-prereqs: ## Transitive prerequisite chain for a course (recursive CTE). Vars: COURSE (id)
	@echo "==> GET /api/courses/$(COURSE)/prerequisites"
	@curl -sS "$(BASE_URL)/api/courses/$(COURSE)/prerequisites" | $(PRETTY)

semesters: ## List semesters
	@curl -sS $(BASE_URL)/api/semesters | $(PRETTY)

enroll: ## STEP 4 -- Enroll in a course. Vars: COURSE (id), SEMESTER (id, default: active semester)
	@echo "==> POST /api/me/enrollments   ->   SELECT ... FOR UPDATE, capacity check, INSERT (one transaction)"
	@sem=$(SEMESTER); \
	if [ -z "$$sem" ]; then sem=$$(curl -sS $(BASE_URL)/api/semesters/active | jq -r .semester_id); fi; \
	curl -sS -b $(STUDENT_JAR) -X POST $(BASE_URL)/api/me/enrollments \
	  -H 'Content-Type: application/json' \
	  -d "{\"course_id\":$(COURSE),\"semester_id\":$$sem}" | $(PRETTY)

my-enrollments: ## STEP 5 -- View your enrollments
	@curl -sS -b $(STUDENT_JAR) $(BASE_URL)/api/me/enrollments | $(PRETTY)

my-attendance: ## View attendance for one of your enrollments. Vars: ENROLLMENT (id, required)
	@if [ -z "$(ENROLLMENT)" ]; then echo "Usage: make my-attendance ENROLLMENT=<enrollment_id>"; exit 1; fi
	@curl -sS -b $(STUDENT_JAR) $(BASE_URL)/api/enrollments/$(ENROLLMENT)/attendance | $(PRETTY)

my-grades: ## STEP 6 -- View your computed grades
	@curl -sS -b $(STUDENT_JAR) $(BASE_URL)/api/me/grades | $(PRETTY)

my-payments: ## STEP 7 -- View your fee invoices
	@curl -sS -b $(STUDENT_JAR) $(BASE_URL)/api/me/payments | $(PRETTY)

pay: ## Pay one of your invoices. Vars: PAYMENT (id, required), METHOD (card/bank_transfer/cash)
	@if [ -z "$(PAYMENT)" ]; then echo "Usage: make pay PAYMENT=<payment_id> [METHOD=card]"; exit 1; fi
	@curl -sS -b $(STUDENT_JAR) -X POST $(BASE_URL)/api/me/payments/$(PAYMENT)/pay \
	  -H 'Content-Type: application/json' -d '{"method":"$(METHOD)"}' | $(PRETTY)

certificate: ## STEP 8 -- Request a certificate (402 PaymentRequiredError if any semester is unpaid). Vars: CERT_TYPE
	@echo "==> POST /api/me/certificates"
	@curl -sS -b $(STUDENT_JAR) -X POST $(BASE_URL)/api/me/certificates \
	  -H 'Content-Type: application/json' -d '{"type":"$(CERT_TYPE)"}' | $(PRETTY)

my-certificates: ## List your issued certificates
	@curl -sS -b $(STUDENT_JAR) $(BASE_URL)/api/me/certificates | $(PRETTY)

##@ Step by step: Admin (session persists in $(ADMIN_JAR))

admin-login: ## Log in as admin (demo mode: any email/password works, account auto-created if new; defaults to the seeded admin@ems.test)
	@echo "==> POST /api/auth/admin/login   ->   auto-creates the admin if the email isn't found; password isn't checked"
	@curl -sS -c $(ADMIN_JAR) -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/auth/admin/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"admin@ems.test","password":"admin-123"}' | $(PRETTY)

admin-me: ## Show the current admin session
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/auth/me | $(PRETTY)

record-attendance: ## Record attendance for an enrollment. Vars: ENROLLMENT (id, required), STATUS, SESSION_DATE
	@if [ -z "$(ENROLLMENT)" ]; then echo "Usage: make record-attendance ENROLLMENT=<id> [STATUS=present] [SESSION_DATE=YYYY-MM-DD]"; exit 1; fi
	@echo "==> POST /api/enrollments/$(ENROLLMENT)/attendance   ->   UNIQUE(enrollment_id, session_date) -- one row per day"
	@curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/enrollments/$(ENROLLMENT)/attendance \
	  -H 'Content-Type: application/json' \
	  -d '{"session_date":"$(SESSION_DATE)","status":"$(STATUS)"}' | $(PRETTY)

record-exam-result: ## Record/upsert an exam result. Vars: EXAM (id, required), STUDENT (id, required), MARKS
	@if [ -z "$(EXAM)" ] || [ -z "$(STUDENT)" ]; then echo "Usage: make record-exam-result EXAM=<id> STUDENT=<id> [MARKS=80]"; exit 1; fi
	@echo "==> POST /api/exams/$(EXAM)/results   ->   INSERT ... ON CONFLICT DO UPDATE (a re-grade overwrites)"
	@curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/exams/$(EXAM)/results \
	  -H 'Content-Type: application/json' \
	  -d '{"student_id":$(STUDENT),"marks_obtained":$(MARKS)}' | $(PRETTY)

compute-grade: ## Finalize a grade from exam + assignment marks. Vars: ENROLLMENT (id, required)
	@if [ -z "$(ENROLLMENT)" ]; then echo "Usage: make compute-grade ENROLLMENT=<enrollment_id>"; exit 1; fi
	@echo "==> POST /api/enrollments/$(ENROLLMENT)/compute-grade"
	@curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/enrollments/$(ENROLLMENT)/compute-grade | $(PRETTY)

create-invoice: ## Raise a fee invoice for a student. Vars: STUDENT (id, required), SEMESTER (id, required)
	@if [ -z "$(STUDENT)" ] || [ -z "$(SEMESTER)" ]; then echo "Usage: make create-invoice STUDENT=<id> SEMESTER=<id>"; exit 1; fi
	@curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/students/$(STUDENT)/payments \
	  -H 'Content-Type: application/json' -d '{"semester_id":$(SEMESTER),"amount":48000}' | $(PRETTY)

directory-search: ## Full-text search the teacher/student directory. Vars: TYPE (teachers|students), Q (query)
	@echo "==> GET /api/$(TYPE)/search?q=$(Q)   ->   WHERE to_tsvector('english', name) @@ plainto_tsquery(...)"
	@curl -sS -b $(ADMIN_JAR) "$(BASE_URL)/api/$(TYPE)/search?q=$(Q)" | $(PRETTY)

##@ Reports (Module 9: the advanced PostgreSQL showcase)

report-departments: ## Department rollup report (CTE)
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/reports/departments | $(PRETTY)

report-gpa: ## GPA rankings, overall + per-department (window functions). Vars: DEPARTMENT (id, optional)
	@curl -sS -b $(ADMIN_JAR) "$(BASE_URL)/api/reports/gpa-rankings$(if $(DEPARTMENT),?department_id=$(DEPARTMENT),)" | $(PRETTY)

report-toppers: ## Rank students within one course (window function). Vars: COURSE (id)
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/reports/courses/$(COURSE)/toppers | $(PRETTY)

report-semesters: ## Per-semester report (reads the materialized view)
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/reports/semesters | $(PRETTY)

report-refresh: ## Refresh the semester materialized view (REFRESH MATERIALIZED VIEW CONCURRENTLY)
	@echo "==> POST /api/reports/semesters/refresh"
	@curl -sS -b $(ADMIN_JAR) -X POST $(BASE_URL)/api/reports/semesters/refresh | $(PRETTY)

dashboard-admin: ## Admin summary dashboard (view)
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/reports/admin-dashboard | $(PRETTY)

jsonb-late-penalty: ## Assignments with a late penalty (JSONB key-existence: settings ? 'late_penalty')
	@curl -sS -b $(ADMIN_JAR) $(BASE_URL)/api/assignments/late-penalty | $(PRETTY)

jsonb-due-before: ## Assignments due before a date (JSONB field extraction + cast). Vars: DUE_DATE
	@curl -sS -b $(ADMIN_JAR) "$(BASE_URL)/api/assignments/due-before?date=$(DUE_DATE)" | $(PRETTY)

##@ All-in-one

demo: ## Run the entire lifecycle above in one narrated command (safe to re-run)
	@BASE_URL=$(BASE_URL) STUDENT_JAR=$(STUDENT_JAR) ADMIN_JAR=$(ADMIN_JAR) bash scripts/api_walkthrough.sh
