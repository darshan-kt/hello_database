#!/usr/bin/env bash
# Narrated end-to-end walkthrough: a staff member asks a grounded
# question, an out-of-scope question (to see the "I don't know" guard),
# and a follow-up; an admin uploads a new document and runs the
# evaluation harness. Invoked by `make demo`.
#
# The local LLM is slow on CPU -- this script uses generous curl
# timeouts and says so before each question.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5002}"
STAFF_JAR="${STAFF_JAR:-.staff_cookies.txt}"
ADMIN_JAR="${ADMIN_JAR:-.admin_cookies.txt}"

if ! command -v jq >/dev/null 2>&1; then
  echo "This script uses 'jq' to pretty-print and parse JSON. Install it (e.g. 'sudo apt install jq') and re-run 'make demo'." >&2
  exit 1
fi

step() {
  echo
  echo "———— $1 ————"
  echo "$2"
  echo
}

echo "############################################################"
echo "# Hospital AI Knowledge Assistant -- full lifecycle demo"
echo "############################################################"

step "STEP 1/7 -- Log in as staff" \
  "POST /api/auth/login   ->   demo mode: any email/password works (see docs/01_requirements.md)"
curl -sS -c "$STAFF_JAR" -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo.staff@hospital.test","password":"learn-123"}' | jq .

step "STEP 2/7 -- Ask a grounded question" \
  "POST /api/chat/ask   ->   embed question -> pgvector similarity search -> grounded prompt -> LLM generate
   (first call on a fresh container downloads+loads the local model: budget up to ~90s. Warm calls: ~10-15s.)"
ASK1=$(curl -sS -b "$STAFF_JAR" -X POST "$BASE_URL/api/chat/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the treatment protocol for dengue fever?"}' --max-time 180)
echo "$ASK1" | jq '{answer, model, citations: [.citations[] | {document_title, similarity}]}'
CONVERSATION_ID=$(echo "$ASK1" | jq -r .conversation_id)

step "STEP 3/7 -- Ask something the documents don't cover" \
  "Retrieval finds nothing above the similarity floor -> the LLM is never called (deterministic guard, see chat_service.py)"
curl -sS -b "$STAFF_JAR" -X POST "$BASE_URL/api/chat/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the capital of France?"}' --max-time 30 | jq '{answer, model, citations}'

step "STEP 4/7 -- Follow-up question in the same conversation" \
  "Conversation history is injected into the prompt -- but the follow-up must still name the topic
   (retrieval doesn't rewrite it with history first; see the 'Known limitation' in docs/01_requirements.md)"
curl -sS -b "$STAFF_JAR" -X POST "$BASE_URL/api/chat/ask" \
  -H 'Content-Type: application/json' \
  -d "{\"question\":\"What about severe dengue cases specifically?\",\"conversation_id\":$CONVERSATION_ID}" \
  --max-time 60 | jq '{answer, model}'

step "STEP 5/7 -- Admin logs in and uploads a new document" \
  "POST /api/documents (multipart)   ->   extract -> chunk -> embed -> store, with file-hash dedup"
curl -sS -c "$ADMIN_JAR" -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' -d '{"email":"admin@hospital.test","password":"admin-123"}' > /dev/null
TMP_DOC=$(mktemp --suffix=.txt)
echo "Fire Safety Protocol: activate the nearest alarm pull station, evacuate via the marked stairwell, and assemble at the designated muster point. Do not use elevators during a fire alarm." > "$TMP_DOC"
curl -sS -b "$ADMIN_JAR" -X POST "$BASE_URL/api/documents" \
  -F "file=@${TMP_DOC};filename=fire_safety_protocol.txt" --max-time 30 | jq .
rm -f "$TMP_DOC"

step "STEP 6/7 -- Re-upload the exact same file (dedup demo)" \
  "hospital_documents.file_hash is UNIQUE -> 409 DuplicateDocumentError, not a silent re-embed"
TMP_DOC2=$(mktemp --suffix=.txt)
echo "Fire Safety Protocol: activate the nearest alarm pull station, evacuate via the marked stairwell, and assemble at the designated muster point. Do not use elevators during a fire alarm." > "$TMP_DOC2"
curl -sS -b "$ADMIN_JAR" -X POST "$BASE_URL/api/documents" \
  -F "file=@${TMP_DOC2};filename=fire_safety_protocol.txt" --max-time 30 | jq . || true
rm -f "$TMP_DOC2"

step "STEP 7/7 -- Run the evaluation harness" \
  "GET /api/evaluation/run   ->   semantic vs. lexical recall/precision against the labeled question set"
curl -sS -b "$ADMIN_JAR" "$BASE_URL/api/evaluation/run" --max-time 30 | \
  jq '{avg_semantic_recall, avg_semantic_precision, avg_lexical_recall}'

echo
echo "Demo complete. Now try the failure paths and advanced queries yourself:"
echo "  make ask Q=\"What is the capital of France?\"          # no-context guard again"
echo "  make upload FILE=scripts/sample_documents/hand_hygiene_sop.md DEPARTMENT=4"
echo "  make explain                                            # HNSW index EXPLAIN ANALYZE evidence"
echo "  make benchmark-vector-index                              # reproduce docs/03_optimization.md yourself"
