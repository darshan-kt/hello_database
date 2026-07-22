#!/usr/bin/env bash
# Narrated end-to-end walkthrough of the EMS API: a new student enrolls,
# an admin records attendance/exam results and finalizes a grade, the
# student pays their fee and gets a certificate, and the admin runs the
# Module 9 reports. Invoked by `make demo`.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5001}"
STUDENT_JAR="${STUDENT_JAR:-.student_cookies.txt}"
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

EMAIL="demo.$(date +%s)@ems.test"

echo "############################################################"
echo "# EMS full lifecycle demo -- fresh account: $EMAIL"
echo "############################################################"

step "STEP 1/11 -- Register a student" \
  "POST /api/auth/student/register   ->   INSERT INTO students (...)   [DuplicateEmailError -> 409 if taken]"
DEPTS=$(curl -sS "$BASE_URL/api/departments")
CS_DEPT_ID=$(echo "$DEPTS" | jq -r '[.[] | select(.code=="CS")][0].department_id')
STUDENT=$(curl -sS -c "$STUDENT_JAR" -b "$STUDENT_JAR" -X POST "$BASE_URL/api/auth/student/register" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Demo Learner\",\"email\":\"$EMAIL\",\"password\":\"learn-123\",\"department_id\":$CS_DEPT_ID}")
echo "$STUDENT" | jq .
STUDENT_ID=$(echo "$STUDENT" | jq -r .student_id)

step "STEP 2/11 -- Browse departments (recursive CTE hierarchy)" \
  "GET /api/departments/hierarchy   ->   WITH RECURSIVE dept_tree AS (...)"
curl -sS "$BASE_URL/api/departments/hierarchy" | jq '.[] | {path, code}'

step "STEP 3/11 -- Full-text search courses" \
  "GET /api/courses/search?q=programming   ->   SELECT ... WHERE search_vector @@ plainto_tsquery(...)"
COURSE=$(curl -sS "$BASE_URL/api/courses/search?q=programming" | jq -r '.[0]')
echo "$COURSE" | jq .
COURSE_ID=$(echo "$COURSE" | jq -r .course_id)

step "STEP 4/11 -- View this course's prerequisite chain (recursive CTE)" \
  "GET /api/courses/$COURSE_ID/prerequisites"
curl -sS "$BASE_URL/api/courses/$COURSE_ID/prerequisites" | jq .

step "STEP 5/11 -- Enroll in the active semester" \
  "POST /api/me/enrollments   ->   SELECT ... FOR UPDATE (locks the course row), INSERT enrollments"
SEMESTER_ID=$(curl -sS "$BASE_URL/api/semesters/active" | jq -r .semester_id)
ENROLLMENT=$(curl -sS -b "$STUDENT_JAR" -X POST "$BASE_URL/api/me/enrollments" \
  -H 'Content-Type: application/json' -d "{\"course_id\":$COURSE_ID,\"semester_id\":$SEMESTER_ID}")
echo "$ENROLLMENT" | jq .
ENROLLMENT_ID=$(echo "$ENROLLMENT" | jq -r .enrollment_id)

step "STEP 6/11 -- Admin logs in and records attendance for this enrollment" \
  "POST /api/auth/admin/login, then POST /api/enrollments/$ENROLLMENT_ID/attendance"
curl -sS -c "$ADMIN_JAR" -X POST "$BASE_URL/api/auth/admin/login" \
  -H 'Content-Type: application/json' -d '{"email":"admin@ems.test","password":"admin-123"}' | jq .
curl -sS -b "$ADMIN_JAR" -X POST "$BASE_URL/api/enrollments/$ENROLLMENT_ID/attendance" \
  -H 'Content-Type: application/json' -d "{\"session_date\":\"$(date +%F)\",\"status\":\"present\"}" | jq .

step "STEP 7/11 -- Admin records an exam result for this student" \
  "POST /api/exams/<id>/results   ->   INSERT ... ON DUPLICATE KEY UPDATE (a re-grade overwrites, doesn't error)"
EXAM_ID=$(curl -sS "$BASE_URL/api/courses/$COURSE_ID/exams" | jq -r '[.[] | select(.name=="Midterm")][0].exam_id')
curl -sS -b "$ADMIN_JAR" -X POST "$BASE_URL/api/exams/$EXAM_ID/results" \
  -H 'Content-Type: application/json' -d "{\"student_id\":$STUDENT_ID,\"marks_obtained\":44}" | jq .

step "STEP 8/11 -- Admin computes the final grade" \
  "POST /api/enrollments/$ENROLLMENT_ID/compute-grade   ->   exam + assignment marks -> percent -> letter -> GPA points"
curl -sS -b "$ADMIN_JAR" -X POST "$BASE_URL/api/enrollments/$ENROLLMENT_ID/compute-grade" | jq .

step "STEP 9/11 -- Admin raises a fee invoice, student pays it" \
  "POST /api/students/$STUDENT_ID/payments, then POST /api/me/payments/<id>/pay"
PAYMENT=$(curl -sS -b "$ADMIN_JAR" -X POST "$BASE_URL/api/students/$STUDENT_ID/payments" \
  -H 'Content-Type: application/json' -d "{\"semester_id\":$SEMESTER_ID,\"amount\":48000}")
echo "$PAYMENT" | jq .
PAYMENT_ID=$(echo "$PAYMENT" | jq -r .payment_id)
curl -sS -b "$STUDENT_JAR" -X POST "$BASE_URL/api/me/payments/$PAYMENT_ID/pay" \
  -H 'Content-Type: application/json' -d '{"method":"card"}' | jq .

step "STEP 10/11 -- Student requests a certificate (would 402 if unpaid -- see docs/04)" \
  "POST /api/me/certificates"
curl -sS -b "$STUDENT_JAR" -X POST "$BASE_URL/api/me/certificates" \
  -H 'Content-Type: application/json' -d '{"type":"transcript"}' | jq .

step "STEP 11/11 -- Admin runs the Module 9 reports" \
  "GPA rankings (window fn), department report (CTE), semester report (materialized view)"
echo "-- GPA rankings (top 3) --"
curl -sS -b "$ADMIN_JAR" "$BASE_URL/api/reports/gpa-rankings" | jq '.[0:3]'
echo "-- Department report --"
curl -sS -b "$ADMIN_JAR" "$BASE_URL/api/reports/departments" | jq '.[0:3]'
echo "-- Semester report (materialized view) --"
curl -sS -b "$ADMIN_JAR" "$BASE_URL/api/reports/semesters" | jq .

echo
echo "Demo complete. Now try the failure paths yourself:"
echo "  make enroll COURSE=$COURSE_ID SEMESTER=$SEMESTER_ID     # already enrolled -> 409"
echo "  make register EMAIL=$EMAIL                              # duplicate email -> 409"
echo "  make report-toppers COURSE=$COURSE_ID                   # window fn ranking within one course"
