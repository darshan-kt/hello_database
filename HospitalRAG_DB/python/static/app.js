const state = {
  role: null,
  departments: [],
  deptNameById: {},
  currentConversationId: null,
};

// ---------------------------------------------------------------- helpers
async function api(path, options = {}) {
  const res = await fetch(path, {
    method: options.method || "GET",
    headers: options.isFormData ? undefined : { "Content-Type": "application/json" },
    body: options.isFormData ? options.body : options.body ? JSON.stringify(options.body) : undefined,
  });
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    const err = new Error((data && (data.error || data.detail)) || res.statusText);
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
  toast._t = setTimeout(() => el.classList.add("hidden"), 4500);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ---------------------------------------------------------------- bootstrap
async function loadReferenceData() {
  state.departments = await api("/api/departments");
  state.deptNameById = Object.fromEntries(state.departments.map((d) => [d.department_id, d.name]));
}

function populateDepartmentSelect(select, placeholder) {
  select.innerHTML = "";
  if (placeholder) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = placeholder;
    select.appendChild(opt);
  }
  state.departments.forEach((d) => {
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
      document.getElementById("staff-auth").classList.toggle("hidden", role !== "staff");
      document.getElementById("admin-auth").classList.toggle("hidden", role !== "admin");
    });
  });
}

async function handleStaffLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/auth/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    onLoggedIn("staff", user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/auth/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    if (user.role !== "admin") {
      toast("That account is not an admin account.", "error");
      return;
    }
    onLoggedIn("admin", user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleLogout() {
  await api("/api/auth/logout", { method: "POST" });
  state.role = null;
  document.getElementById("staff-screen").classList.add("hidden");
  document.getElementById("admin-screen").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("auth-status").innerHTML = "";
}

async function onLoggedIn(role, user) {
  state.role = role;
  await loadReferenceData();

  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("auth-status").innerHTML =
    `<span class="role-badge">${role}</span> Signed in as <strong>${user.name}</strong> <button id="logout-btn">Log out</button>`;
  document.getElementById("logout-btn").addEventListener("click", handleLogout);

  if (role === "staff") {
    document.getElementById("staff-screen").classList.remove("hidden");
    document.getElementById("admin-screen").classList.add("hidden");
    initChat();
  } else {
    document.getElementById("admin-screen").classList.remove("hidden");
    document.getElementById("staff-screen").classList.add("hidden");
    initAdminConsole();
  }
}

// ================================================================== CHAT
function initChat() {
  populateDepartmentSelect(document.getElementById("chat-department-filter"), "All departments");
  loadConversations();
}

async function loadConversations() {
  const list = await api("/api/conversations");
  const el = document.getElementById("conversation-list");
  el.innerHTML = "";
  list.forEach((c) => {
    const item = document.createElement("div");
    item.className = "conversation-item" + (c.conversation_id === state.currentConversationId ? " active" : "");
    item.textContent = c.title || `Conversation #${c.conversation_id}`;
    item.addEventListener("click", () => openConversation(c.conversation_id));
    el.appendChild(item);
  });
}

async function openConversation(conversationId) {
  state.currentConversationId = conversationId;
  document.querySelectorAll(".conversation-item").forEach((el) => el.classList.remove("active"));
  const rows = await api(`/api/conversations/${conversationId}/messages`);
  const box = document.getElementById("chat-messages");
  box.innerHTML = "";
  rows.forEach((m) => appendBubble(m.role, m.content, m.citations || []));
  loadConversations();
}

function newChat() {
  state.currentConversationId = null;
  document.getElementById("chat-messages").innerHTML =
    '<div class="chat-empty">Ask a question grounded in the hospital\'s documents.</div>';
  document.querySelectorAll(".conversation-item").forEach((el) => el.classList.remove("active"));
}

function appendBubble(role, content, citations) {
  const box = document.getElementById("chat-messages");
  const empty = box.querySelector(".chat-empty");
  if (empty) empty.remove();

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = content;

  if (citations && citations.length) {
    const details = document.createElement("details");
    details.className = "citations";
    const summary = document.createElement("summary");
    summary.textContent = `${citations.length} source${citations.length > 1 ? "s" : ""}`;
    details.appendChild(summary);
    citations.forEach((c, i) => {
      const div = document.createElement("div");
      div.className = "citation-item";
      const score = c.similarity_score ?? c.similarity;
      // The immediate /api/chat/ask response returns raw retriever
      // results (no `rank` field -- that's only added once a citation
      // is persisted via MessageRepository.add_citations). Falling back
      // to the array position keeps the numbering correct either way.
      const rank = c.rank || i + 1;
      div.innerHTML = `<strong>[${rank}] ${escapeHtml(c.document_title)}</strong> (similarity ${Number(score).toFixed(2)})<br>${escapeHtml((c.content || "").slice(0, 200))}...`;
      details.appendChild(div);
    });
    bubble.appendChild(details);
  }

  box.appendChild(bubble);
  box.scrollTop = box.scrollHeight;
  return bubble;
}

async function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const question = input.value.trim();
  if (!question) return;

  const sendBtn = document.getElementById("chat-send-btn");
  const departmentId = document.getElementById("chat-department-filter").value || null;

  appendBubble("user", question, []);
  input.value = "";
  sendBtn.disabled = true;
  const pending = appendBubble(
    "pending",
    "Thinking... (the local model can take up to a minute on first use, and ~10-15s per answer after that)",
    []
  );

  try {
    const result = await api("/api/chat/ask", {
      method: "POST",
      body: { question, conversation_id: state.currentConversationId, department_id: departmentId },
    });
    pending.remove();
    appendBubble("assistant", result.answer, result.citations);
    const wasNewConversation = state.currentConversationId === null;
    state.currentConversationId = result.conversation_id;
    if (wasNewConversation) loadConversations();
  } catch (err) {
    pending.remove();
    appendBubble("assistant", `Error: ${err.message}`, []);
    toast(err.message, "error");
  } finally {
    sendBtn.disabled = false;
  }
}

// ================================================================== ADMIN
function initAdminConsole() {
  populateDepartmentSelect(document.getElementById("upload-department-select"), "No department");
  loadDocuments();
  loadDepartments();
}

function wirePageTabs() {
  document.querySelectorAll("#admin-screen .page-tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#admin-screen .page-tabs .tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const page = btn.dataset.page;
      document.querySelectorAll("#admin-screen .page").forEach((p) => p.classList.toggle("hidden", p.id !== `page-${page}`));
      if (page === "a-audit") loadAuditLog();
    });
  });
}

async function loadDocuments() {
  const rows = await api("/api/documents");
  const table = document.getElementById("documents-table");
  table.innerHTML = `
    <tr><th>Title</th><th>Type</th><th>Department</th><th>Status</th><th>Uploaded</th><th></th></tr>
    ${rows.map((d) => `
      <tr>
        <td>${escapeHtml(d.title)}</td>
        <td>${d.source_type}</td>
        <td>${state.deptNameById[d.department_id] || "--"}</td>
        <td><span class="status-badge status-${d.status}">${d.status}</span>${d.error_message ? ` <span class="hint">${escapeHtml(d.error_message)}</span>` : ""}</td>
        <td>${new Date(d.uploaded_at).toLocaleString()}</td>
        <td><button data-id="${d.document_id}" class="delete-doc-btn">Delete</button></td>
      </tr>`).join("")}
  `;
  table.querySelectorAll(".delete-doc-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/documents/${btn.dataset.id}`, { method: "DELETE" });
      toast("Document deleted", "success");
      loadDocuments();
    });
  });
}

async function handleUploadSubmit(e) {
  e.preventDefault();
  const fileInput = document.getElementById("upload-file-input");
  const departmentId = document.getElementById("upload-department-select").value;
  const status = document.getElementById("upload-status");
  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  if (departmentId) formData.append("department_id", departmentId);

  status.textContent = "Uploading and ingesting (extract -> chunk -> embed -> store)...";
  try {
    const result = await api("/api/documents", { method: "POST", body: formData, isFormData: true });
    status.textContent = `Done: ${result.chunks_stored} chunks stored, ${result.chunks_skipped_duplicate} skipped as duplicates.`;
    fileInput.value = "";
    loadDocuments();
  } catch (err) {
    status.textContent = "";
    toast(err.message, "error");
  }
}

async function loadDepartments() {
  const rows = await api("/api/departments");
  const table = document.getElementById("departments-table");
  table.innerHTML = `
    <tr><th>Name</th><th>Code</th></tr>
    ${rows.map((d) => `<tr><td>${escapeHtml(d.name)}</td><td>${escapeHtml(d.code)}</td></tr>`).join("")}
  `;
}

async function handleDepartmentSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("dept-name-input").value.trim();
  const code = document.getElementById("dept-code-input").value.trim();
  if (!name || !code) return;
  try {
    await api("/api/departments", { method: "POST", body: { name, code } });
    document.getElementById("dept-name-input").value = "";
    document.getElementById("dept-code-input").value = "";
    await loadReferenceData();
    loadDepartments();
    toast("Department added", "success");
  } catch (err) {
    toast(err.message, "error");
  }
}

async function runEvaluation() {
  const status = document.getElementById("eval-status");
  status.textContent = "Running (embeds each question, runs semantic + lexical search)...";
  try {
    const result = await api("/api/evaluation/run");
    status.textContent = "";
    document.getElementById("eval-summary").innerHTML = `
      <div class="stat-card"><div class="value">${(result.avg_semantic_recall * 100).toFixed(0)}%</div><div class="label">Avg Semantic Recall</div></div>
      <div class="stat-card"><div class="value">${(result.avg_semantic_precision * 100).toFixed(0)}%</div><div class="label">Avg Semantic Precision</div></div>
      <div class="stat-card"><div class="value">${(result.avg_lexical_recall * 100).toFixed(0)}%</div><div class="label">Avg Lexical Recall</div></div>
    `;
    document.getElementById("eval-table").innerHTML = `
      <tr><th>Question</th><th>Semantic Recall</th><th>Semantic Precision</th><th>Lexical Recall</th></tr>
      ${result.cases.map((c) => `
        <tr>
          <td>${escapeHtml(c.question)}</td>
          <td>${(c.semantic_recall * 100).toFixed(0)}%</td>
          <td>${(c.semantic_precision * 100).toFixed(0)}%</td>
          <td>${(c.lexical_recall * 100).toFixed(0)}%</td>
        </tr>`).join("")}
    `;
  } catch (err) {
    status.textContent = "";
    toast(err.message, "error");
  }
}

async function loadAuditLog() {
  const rows = await api("/api/audit");
  const table = document.getElementById("audit-table");
  table.innerHTML = `
    <tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>
    ${rows.map((a) => `
      <tr>
        <td>${new Date(a.created_at).toLocaleString()}</td>
        <td>${escapeHtml(a.user_name || "--")}</td>
        <td>${a.action}</td>
        <td><code>${escapeHtml(JSON.stringify(a.detail))}</code></td>
      </tr>`).join("")}
  `;
}

// ---------------------------------------------------------------- wiring
document.addEventListener("DOMContentLoaded", async () => {
  wireAuthTabs();
  document.getElementById("staff-login-form").addEventListener("submit", handleStaffLogin);
  document.getElementById("admin-login-form").addEventListener("submit", handleAdminLogin);
  document.getElementById("new-chat-btn").addEventListener("click", newChat);
  document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
  wirePageTabs();
  document.getElementById("upload-form").addEventListener("submit", handleUploadSubmit);
  document.getElementById("department-form").addEventListener("submit", handleDepartmentSubmit);
  document.getElementById("run-eval-btn").addEventListener("click", runEvaluation);

  try {
    const me = await api("/api/auth/me");
    onLoggedIn(me.role, me);
  } catch {
    /* not logged in */
  }
});
