const state = {
  role: null,
  departments: [],
  deptNameById: {},
  semesters: [],
  activeSemesterId: null,
  gradesByEnrollment: {},
};

// ---------------------------------------------------------------- helpers
async function api(path, options = {}) {
  const res = await fetch(path, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    const err = new Error((data && data.error) || res.statusText);
    err.status = res.status;
    err.type = data && data.type;
    throw err;
  }
  return data;
}

function toast(message, type = "info") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast ${type}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 4000);
}

function money(n) {
  return Number(n).toFixed(2);
}

function fmt(n, digits = 2) {
  return n === null || n === undefined ? "--" : Number(n).toFixed(digits);
}

// ---------------------------------------------------------------- bootstrap
async function loadReferenceData() {
  state.departments = await api("/api/departments");
  state.deptNameById = Object.fromEntries(state.departments.map((d) => [d.department_id, d.name]));
  state.semesters = await api("/api/semesters");
  try {
    const active = await api("/api/semesters/active");
    state.activeSemesterId = active.semester_id;
  } catch {
    state.activeSemesterId = state.semesters[0]?.semester_id;
  }
}

function populateDepartmentSelect(select, { includeSchools = false, placeholder = null } = {}) {
  // The placeholder must be appended first, into the empty select --
  // a <select> auto-selects whichever option is first at the moment it
  // stops being empty, and inserting one before an already-selected
  // option later does *not* move the selection back to it.
  select.innerHTML = "";
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.appendChild(opt);
  }
  state.departments
    .filter((d) => includeSchools || d.parent_department_id !== null)
    .forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.department_id;
      opt.textContent = d.name;
      select.appendChild(opt);
    });
}

// ---------------------------------------------------------------- auth
function wireAuthTabs() {
  document.querySelectorAll('#auth-screen > .auth-card > .tabs > .tab').forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll('#auth-screen > .auth-card > .tabs > .tab').forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const role = btn.dataset.role;
      document.getElementById("student-auth").classList.toggle("hidden", role !== "student");
      document.getElementById("admin-auth").classList.toggle("hidden", role !== "admin");
    });
  });

  document.querySelectorAll(".subtabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".subtabs .tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const sub = btn.dataset.subtab;
      document.getElementById("student-login-form").classList.toggle("hidden", sub !== "student-login");
      document.getElementById("student-register-form").classList.toggle("hidden", sub !== "student-register");
    });
  });
}

async function handleStudentLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/auth/student/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    onLoggedIn("student", user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleStudentRegister(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/auth/student/register", {
      method: "POST",
      body: {
        name: form.get("name"),
        email: form.get("email"),
        password: form.get("password"),
        department_id: parseInt(form.get("department_id"), 10),
      },
    });
    toast(`Welcome, ${user.name}!`, "success");
    onLoggedIn("student", user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/auth/admin/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    onLoggedIn("admin", user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleLogout() {
  await api("/api/auth/logout", { method: "POST" });
  state.role = null;
  document.getElementById("student-screen").classList.add("hidden");
  document.getElementById("admin-screen").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("auth-status").innerHTML = "";
}

async function onLoggedIn(role, user) {
  state.role = role;
  await loadReferenceData();

  document.getElementById("auth-screen").classList.add("hidden");
  const badge = `<span class="role-badge">${role}</span>`;
  document.getElementById("auth-status").innerHTML =
    `${badge} Signed in as <strong>${user.name}</strong> <button id="logout-btn">Log out</button>`;
  document.getElementById("logout-btn").addEventListener("click", handleLogout);

  if (role === "student") {
    document.getElementById("student-screen").classList.remove("hidden");
    document.getElementById("admin-screen").classList.add("hidden");
    initStudentPortal();
  } else {
    document.getElementById("admin-screen").classList.remove("hidden");
    document.getElementById("student-screen").classList.add("hidden");
    initAdminConsole();
  }
}

// ================================================================== STUDENT
function initStudentPortal() {
  loadStudentDashboard();
  loadCourses();
  renderDepartmentFilterBar();
}

function wirePageTabs(scopeSelector) {
  document.querySelectorAll(`${scopeSelector} .page-tabs .tab`).forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(`${scopeSelector} .page-tabs .tab`).forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const page = btn.dataset.page;
      document.querySelectorAll(`${scopeSelector} .page`).forEach((p) => {
        p.classList.toggle("hidden", p.id !== `page-${page}`);
      });
      if (page === "s-enrollments") loadEnrollments();
      if (page === "s-payments") loadPayments();
      if (page === "s-certificates") loadCertificates();
    });
  });
}

async function loadStudentDashboard() {
  const d = await api("/api/me/dashboard");
  const el = document.getElementById("student-stats");
  el.innerHTML = `
    <div class="stat-card"><div class="value">${fmt(d.gpa)}</div><div class="label">GPA</div></div>
    <div class="stat-card"><div class="value">${d.attendance_pct ?? "--"}%</div><div class="label">Attendance</div></div>
    <div class="stat-card"><div class="value">${d.total_enrollments}</div><div class="label">Enrollments</div></div>
    <div class="stat-card"><div class="value">${d.pending_payments}</div><div class="label">Pending Payments</div></div>
  `;
}

function renderDepartmentFilterBar() {
  const bar = document.getElementById("department-filter-bar");
  bar.innerHTML = "";
  const allBtn = document.createElement("button");
  allBtn.textContent = "All";
  allBtn.className = "active";
  allBtn.addEventListener("click", () => { setActiveFilterBtn(allBtn); loadCourses(); });
  bar.appendChild(allBtn);
  state.departments
    .filter((d) => d.parent_department_id !== null)
    .forEach((d) => {
      const btn = document.createElement("button");
      btn.textContent = d.name;
      btn.addEventListener("click", () => { setActiveFilterBtn(btn); loadCourses(d.department_id); });
      bar.appendChild(btn);
    });
}

function setActiveFilterBtn(btn) {
  document.querySelectorAll("#department-filter-bar button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
}

async function loadCourses(departmentId) {
  const qs = departmentId ? `?department_id=${departmentId}` : "";
  const items = await api(`/api/courses${qs}`);
  renderCourseGrid(items);
}

async function searchCourses() {
  const q = document.getElementById("course-search-input").value.trim();
  if (!q) return loadCourses();
  const items = await api(`/api/courses/search?q=${encodeURIComponent(q)}`);
  renderCourseGrid(items);
}

function renderCourseGrid(items) {
  const grid = document.getElementById("course-grid");
  grid.innerHTML = "";
  if (items.length === 0) {
    grid.innerHTML = '<p class="hint">No courses match.</p>';
    return;
  }
  items.forEach((c) => grid.appendChild(renderCourseCard(c)));
}

function renderCourseCard(c) {
  const card = document.createElement("div");
  card.className = "product-card";
  const semesterOptions = state.semesters
    .map((s) => `<option value="${s.semester_id}" ${s.semester_id === state.activeSemesterId ? "selected" : ""}>${s.name}</option>`)
    .join("");
  card.innerHTML = `
    <h3>${c.code} -- ${c.title}</h3>
    <div class="meta">${state.deptNameById[c.department_id] || ""} &middot; ${c.credits} credits &middot; capacity ${c.capacity}</div>
    <div class="desc">${c.description || ""}</div>
    <div class="prereqs" data-prereqs></div>
    <select class="semester-select">${semesterOptions}</select>
    <button class="enroll-btn">Enroll</button>
  `;
  const prereqEl = card.querySelector("[data-prereqs]");
  api(`/api/courses/${c.course_id}/prerequisites`).then((chain) => {
    if (chain.length) {
      prereqEl.textContent = `Requires: ${chain.map((p) => p.code).join(" -> ")}`;
    }
  });
  card.querySelector(".enroll-btn").addEventListener("click", async () => {
    const semesterId = parseInt(card.querySelector(".semester-select").value, 10);
    try {
      await api("/api/me/enrollments", { method: "POST", body: { course_id: c.course_id, semester_id: semesterId } });
      toast(`Enrolled in ${c.code}`, "success");
      loadStudentDashboard();
    } catch (err) {
      toast(err.message, "error");
    }
  });
  return card;
}

async function loadEnrollments() {
  const [enrollmentRows, gradeRows] = await Promise.all([
    api("/api/me/enrollments"),
    api("/api/me/grades"),
  ]);
  state.gradesByEnrollment = Object.fromEntries(gradeRows.map((g) => [g.enrollment_id, g]));

  const list = document.getElementById("enrollment-list");
  list.innerHTML = "";
  if (enrollmentRows.length === 0) {
    list.innerHTML = '<p class="hint">No enrollments yet -- browse courses to enroll.</p>';
    return;
  }
  enrollmentRows.forEach((enr) => list.appendChild(renderEnrollmentCard(enr)));
}

function renderEnrollmentCard(enr) {
  const card = document.createElement("div");
  card.className = "order-card";
  const grade = state.gradesByEnrollment[enr.enrollment_id];
  const gradeLine = grade
    ? `<div class="grade-line"><strong>Grade:</strong> ${grade.letter_grade} (${fmt(grade.total_percent)}%, ${fmt(grade.gpa_points)} GPA points)</div>`
    : `<div class="grade-line hint">Grade not yet computed.</div>`;
  card.innerHTML = `
    <div class="order-head">
      <strong>${enr.course_code} -- ${enr.course_title}</strong>
      <span class="status-badge status-${enr.status}">${enr.status}</span>
    </div>
    <div class="sub">${enr.semester_name}</div>
    ${gradeLine}
    <button class="attendance-btn">View attendance</button>
    <div class="attendance-lines hidden"></div>
  `;
  const attendanceBox = card.querySelector(".attendance-lines");
  card.querySelector(".attendance-btn").addEventListener("click", async () => {
    if (!attendanceBox.classList.contains("hidden")) {
      attendanceBox.classList.add("hidden");
      return;
    }
    const rows = await api(`/api/enrollments/${enr.enrollment_id}/attendance`);
    const present = rows.filter((r) => r.status === "present").length;
    attendanceBox.innerHTML = rows.length
      ? `${present}/${rows.length} sessions present (${((100 * present) / rows.length).toFixed(1)}%)`
      : "No sessions recorded yet.";
    attendanceBox.classList.remove("hidden");
  });
  return card;
}

async function loadPayments() {
  const rows = await api("/api/me/payments");
  const list = document.getElementById("payment-list");
  list.innerHTML = "";
  rows.forEach((p) => {
    const card = document.createElement("div");
    card.className = "order-card";
    const payControls =
      p.status === "pending" || p.status === "failed"
        ? `<select class="method-select">
             <option value="card">Card</option>
             <option value="bank_transfer">Bank transfer</option>
             <option value="cash">Cash</option>
           </select>
           <button class="pay-btn">Pay now</button>`
        : "";
    card.innerHTML = `
      <div class="order-head">
        <strong>${p.semester_name}</strong>
        <span class="status-badge status-${p.status}">${p.status}</span>
      </div>
      <div class="sub">Amount due: ₹${money(p.amount)}</div>
      <div class="toolbar" style="margin-top:8px;">${payControls}</div>
    `;
    const payBtn = card.querySelector(".pay-btn");
    if (payBtn) {
      payBtn.addEventListener("click", async () => {
        const method = card.querySelector(".method-select").value;
        try {
          await api(`/api/me/payments/${p.payment_id}/pay`, { method: "POST", body: { method } });
          toast("Payment recorded", "success");
          loadPayments();
          loadStudentDashboard();
        } catch (err) {
          toast(err.message, "error");
        }
      });
    }
    list.appendChild(card);
  });
}

async function loadCertificates() {
  const rows = await api("/api/me/certificates");
  const list = document.getElementById("certificate-list");
  list.innerHTML = rows.length
    ? ""
    : '<p class="hint">No certificates issued yet.</p>';
  rows.forEach((c) => {
    const card = document.createElement("div");
    card.className = "order-card";
    card.innerHTML = `
      <div class="order-head"><strong>${c.type}</strong></div>
      <div class="sub">Verification code: <code>${c.verification_code}</code></div>
      <div class="sub">Issued: ${new Date(c.issued_at).toLocaleDateString()}</div>
    `;
    list.appendChild(card);
  });
}

function wireStudentActions() {
  document.getElementById("course-search-btn").addEventListener("click", searchCourses);
  document.getElementById("course-search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchCourses();
  });
  document.getElementById("request-cert-btn").addEventListener("click", async () => {
    try {
      const result = await api("/api/me/certificates", { method: "POST", body: { type: "transcript" } });
      toast(`Certificate issued: ${result.verification_code}`, "success");
      loadCertificates();
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

// ================================================================== ADMIN
function initAdminConsole() {
  loadAdminDashboard();
  loadDepartmentTree();
  loadDepartmentReport();
  populateDepartmentSelect(document.getElementById("gpa-department-filter"), { placeholder: "All departments" });
}

async function loadAdminDashboard() {
  const d = await api("/api/reports/admin-dashboard");
  const el = document.getElementById("admin-stats");
  el.innerHTML = `
    <div class="stat-card"><div class="value">${d.total_students}</div><div class="label">Students</div></div>
    <div class="stat-card"><div class="value">${d.total_teachers}</div><div class="label">Teachers</div></div>
    <div class="stat-card"><div class="value">${d.total_courses}</div><div class="label">Courses</div></div>
    <div class="stat-card"><div class="value">${d.total_departments}</div><div class="label">Departments</div></div>
    <div class="stat-card"><div class="value">₹${money(d.total_revenue)}</div><div class="label">Revenue collected</div></div>
    <div class="stat-card"><div class="value">${d.pending_payments}</div><div class="label">Pending payments</div></div>
    <div class="stat-card"><div class="value">${fmt(d.overall_avg_gpa)}</div><div class="label">Avg GPA</div></div>
  `;
}

async function loadDepartmentTree() {
  const rows = await api("/api/departments/hierarchy");
  const tree = document.getElementById("department-tree");
  tree.innerHTML = "";
  rows.forEach((r) => {
    const row = document.createElement("div");
    row.className = "tree-row";
    row.style.paddingLeft = `${r.depth * 24}px`;
    row.innerHTML = `${r.depth === 0 ? "\u{1F3EB}" : "└ " }${r.name}<span class="code">${r.code}</span>`;
    tree.appendChild(row);
  });
}

async function loadDepartmentReport() {
  const rows = await api("/api/reports/departments");
  const table = document.getElementById("dept-report-table");
  table.innerHTML = `
    <tr><th>Department</th><th>Students</th><th>Teachers</th><th>Courses</th><th>Avg GPA</th></tr>
    ${rows.map((r) => `
      <tr>
        <td>${r.department_name}</td>
        <td>${r.student_count}</td>
        <td>${r.teacher_count}</td>
        <td>${r.course_count}</td>
        <td>${fmt(r.avg_gpa)}</td>
      </tr>`).join("")}
  `;
}

async function loadGpaRankings() {
  const departmentId = document.getElementById("gpa-department-filter").value;
  const qs = departmentId ? `?department_id=${departmentId}` : "";
  const rows = await api(`/api/reports/gpa-rankings${qs}`);
  const table = document.getElementById("gpa-report-table");
  table.innerHTML = `
    <tr><th>Overall Rank</th><th>Dept Rank</th><th>Student</th><th>Department</th><th>GPA</th></tr>
    ${rows.map((r) => `
      <tr>
        <td>${r.overall_rank}</td>
        <td>${r.department_rank}</td>
        <td>${r.student_name}</td>
        <td>${r.department_name}</td>
        <td>${fmt(r.gpa)}</td>
      </tr>`).join("")}
  `;
}

async function loadSemesterReport() {
  const rows = await api("/api/reports/semesters");
  const table = document.getElementById("semester-report-table");
  table.innerHTML = `
    <tr><th>Semester</th><th>Dates</th><th>Enrollments</th><th>Revenue</th><th>Avg GPA</th><th>Avg Attendance</th></tr>
    ${rows.map((r) => `
      <tr>
        <td>${r.semester_name}</td>
        <td>${r.start_date} &rarr; ${r.end_date}</td>
        <td>${r.enrollment_count}</td>
        <td>₹${money(r.revenue)}</td>
        <td>${fmt(r.avg_gpa)}</td>
        <td>${r.avg_attendance_pct ?? "--"}%</td>
      </tr>`).join("")}
  `;
}

function wireReportTabs() {
  document.querySelectorAll(".report-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".report-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const report = btn.dataset.report;
      document.querySelectorAll(".report-panel").forEach((p) => p.classList.add("hidden"));
      document.getElementById(`report-${report}`).classList.remove("hidden");
      if (report === "gpa") loadGpaRankings();
      if (report === "semester") loadSemesterReport();
    });
  });
  document.getElementById("gpa-department-filter").addEventListener("change", loadGpaRankings);
  document.getElementById("refresh-semester-btn").addEventListener("click", async () => {
    const status = document.getElementById("refresh-status");
    status.textContent = "Refreshing...";
    await api("/api/reports/semesters/refresh", { method: "POST" });
    await loadSemesterReport();
    status.textContent = `Refreshed at ${new Date().toLocaleTimeString()}`;
  });
}

function wireDirectory() {
  async function runSearch() {
    const type = document.getElementById("directory-type").value;
    const q = document.getElementById("directory-search-input").value.trim();
    const table = document.getElementById("directory-table");
    if (!q) {
      table.innerHTML = '<tr><td class="hint">Type a name to search.</td></tr>';
      return;
    }
    const rows = await api(`/api/${type}/search?q=${encodeURIComponent(q)}`);
    table.innerHTML = `
      <tr><th>Name</th><th>Email</th><th>Department</th></tr>
      ${rows.map((r) => `
        <tr>
          <td>${r.name}</td>
          <td>${r.email}</td>
          <td>${state.deptNameById[r.department_id] || ""}</td>
        </tr>`).join("")}
      ${rows.length === 0 ? '<tr><td class="hint">No matches.</td></tr>' : ""}
    `;
  }
  document.getElementById("directory-search-btn").addEventListener("click", runSearch);
  document.getElementById("directory-search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch();
  });
}

function wireJsonbExplorer() {
  document.getElementById("jsonb-late-penalty-btn").addEventListener("click", async () => {
    const rows = await api("/api/assignments/late-penalty");
    renderJsonbResult(rows);
  });
  document.getElementById("jsonb-due-before-btn").addEventListener("click", async () => {
    const date = document.getElementById("jsonb-due-date-input").value;
    const rows = await api(`/api/assignments/due-before?date=${date}`);
    renderJsonbResult(rows);
  });
}

function renderJsonbResult(rows) {
  const el = document.getElementById("jsonb-result");
  el.innerHTML = rows.length
    ? rows
        .slice(0, 20)
        .map(
          (r) => `<div class="jsonb-item"><strong>${r.title}</strong> (assignment #${r.assignment_id}, course #${r.course_id})
            <pre>${JSON.stringify(r.settings, null, 2)}</pre></div>`
        )
        .join("")
    : '<p class="hint">No matches.</p>';
  if (rows.length > 20) {
    el.insertAdjacentHTML("beforeend", `<p class="hint">...and ${rows.length - 20} more.</p>`);
  }
}

// ---------------------------------------------------------------- wiring
document.addEventListener("DOMContentLoaded", async () => {
  wireAuthTabs();
  document.getElementById("student-login-form").addEventListener("submit", handleStudentLogin);
  document.getElementById("student-register-form").addEventListener("submit", handleStudentRegister);
  document.getElementById("admin-login-form").addEventListener("submit", handleAdminLogin);
  wirePageTabs("#student-screen");
  wirePageTabs("#admin-screen");
  wireStudentActions();
  wireReportTabs();
  wireDirectory();
  wireJsonbExplorer();

  // Departments are public -- populate the registration form's dropdown
  // even before login.
  try {
    const depts = await api("/api/departments");
    state.departments = depts;
    populateDepartmentSelect(document.getElementById("register-department-select"));
  } catch {
    /* backend not reachable yet */
  }

  // If a session cookie is already valid (page refresh), skip the auth screen.
  try {
    const me = await api("/api/auth/me");
    onLoggedIn(me.role, me);
  } catch {
    /* not logged in */
  }
});
