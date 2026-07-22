const state = {
  categories: [],
  activeCategory: null,
  cart: { items: [], total: 0 },
  lastOrder: null,
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
  toast._t = setTimeout(() => el.classList.add("hidden"), 3500);
}

function money(n) {
  return Number(n).toFixed(2);
}

// ---------------------------------------------------------------- auth
function wireAuthTabs() {
  document.querySelectorAll("#auth-screen .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#auth-screen .tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      document.getElementById("login-form").classList.toggle("hidden", tab !== "login");
      document.getElementById("register-form").classList.toggle("hidden", tab !== "register");
    });
  });
}

async function handleLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    onLoggedIn(user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const user = await api("/api/register", {
      method: "POST",
      body: { name: form.get("name"), email: form.get("email"), password: form.get("password") },
    });
    toast(`Welcome, ${user.name}!`, "success");
    onLoggedIn(user);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleLogout() {
  await api("/api/logout", { method: "POST" });
  document.getElementById("app-screen").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("auth-status").innerHTML = "";
}

function onLoggedIn(user) {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app-screen").classList.remove("hidden");
  document.getElementById("auth-status").innerHTML =
    `Signed in as <strong>${user.name}</strong> <button id="logout-btn">Log out</button>`;
  document.getElementById("logout-btn").addEventListener("click", handleLogout);
  loadCategories();
  loadProducts();
  refreshCart();
}

// ---------------------------------------------------------------- catalog
async function loadCategories() {
  state.categories = await api("/api/categories");
  const bar = document.getElementById("category-bar");
  bar.innerHTML = "";
  const allBtn = document.createElement("button");
  allBtn.textContent = "All";
  allBtn.className = "active";
  allBtn.addEventListener("click", () => selectCategory(null, allBtn));
  bar.appendChild(allBtn);
  state.categories.forEach((c) => {
    const btn = document.createElement("button");
    btn.textContent = c.name;
    btn.addEventListener("click", () => selectCategory(c.category_id, btn));
    bar.appendChild(btn);
  });
}

function selectCategory(categoryId, btn) {
  state.activeCategory = categoryId;
  document.querySelectorAll("#category-bar button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  loadProducts();
}

async function loadProducts() {
  const qs = state.activeCategory ? `?category_id=${state.activeCategory}` : "";
  const items = await api(`/api/products${qs}`);
  const grid = document.getElementById("product-grid");
  grid.innerHTML = "";
  items.forEach((p) => grid.appendChild(renderProductCard(p)));
}

function renderProductCard(p) {
  const card = document.createElement("div");
  card.className = "product-card";
  const stockClass = p.stock_quantity === 0 ? "out" : p.stock_quantity <= 5 ? "low" : "";
  card.innerHTML = `
    <h3>${p.name}</h3>
    <div class="price">₹${money(p.price)}</div>
    <div class="stock ${stockClass}">${p.stock_quantity === 0 ? "Out of stock" : p.stock_quantity + " in stock"}</div>
    <input type="number" class="qty-input" min="1" value="1" ${p.stock_quantity === 0 ? "disabled" : ""}>
    <button ${p.stock_quantity === 0 ? "disabled" : ""}>Add to cart</button>
  `;
  const qtyInput = card.querySelector(".qty-input");
  card.querySelector("button").addEventListener("click", async () => {
    try {
      await api("/api/cart/items", {
        method: "POST",
        body: { product_id: p.product_id, quantity: parseInt(qtyInput.value, 10) || 1 },
      });
      toast(`Added ${p.name} to cart`, "success");
      refreshCart();
    } catch (err) {
      toast(err.message, "error");
    }
  });
  return card;
}

// ---------------------------------------------------------------- cart
async function refreshCart() {
  state.cart = await api("/api/cart");
  const list = document.getElementById("cart-items");
  list.innerHTML = "";
  if (state.cart.items.length === 0) {
    list.innerHTML = '<div class="cart-empty">Your cart is empty.</div>';
  }
  state.cart.items.forEach((line) => {
    const row = document.createElement("div");
    row.className = "cart-line";
    row.innerHTML = `
      <span class="name">${line.product_name} × ${line.quantity}</span>
      <span>₹${money(line.unit_price * line.quantity)}</span>
      <button class="remove" title="Remove">×</button>
    `;
    row.querySelector(".remove").addEventListener("click", async () => {
      await api(`/api/cart/items/${line.product_id}`, { method: "DELETE" });
      refreshCart();
    });
    list.appendChild(row);
  });
  document.getElementById("cart-total").textContent = money(state.cart.total);
  document.getElementById("checkout-btn").disabled = state.cart.items.length === 0;
}

async function handleCheckout() {
  try {
    const result = await api("/api/checkout", { method: "POST" });
    state.lastOrder = result;
    openPaymentModal(result);
    refreshCart();
  } catch (err) {
    toast(err.message, "error");
  }
}

// ---------------------------------------------------------------- payment
function openPaymentModal(order) {
  document.getElementById("pm-order-id").textContent = order.order_id;
  document.getElementById("pm-total").textContent = money(order.total_amount);
  document.getElementById("pm-result").textContent = "";
  document.getElementById("pm-result").className = "pm-result";
  document.getElementById("pm-simulate-failure").checked = false;
  document.getElementById("payment-modal").classList.remove("hidden");
}

function closePaymentModal() {
  document.getElementById("payment-modal").classList.add("hidden");
  if (!document.getElementById("page-orders").classList.contains("hidden")) {
    loadOrders();
  }
}

async function handlePay() {
  const method = document.getElementById("pm-method").value;
  const simulateFailure = document.getElementById("pm-simulate-failure").checked;
  const resultEl = document.getElementById("pm-result");
  try {
    const res = await api(`/api/orders/${state.lastOrder.order_id}/pay`, {
      method: "POST",
      body: { method, simulate_failure: simulateFailure },
    });
    if (res.success) {
      resultEl.textContent = "Payment succeeded -- order marked paid.";
      resultEl.className = "pm-result success";
      toast("Payment succeeded", "success");
    } else {
      resultEl.textContent = "Payment declined -- order stays pending, you can retry.";
      resultEl.className = "pm-result error";
      toast("Payment declined", "error");
    }
  } catch (err) {
    resultEl.textContent = err.message;
    resultEl.className = "pm-result error";
  }
}

// ---------------------------------------------------------------- orders
function wirePageTabs() {
  document.querySelectorAll(".page-tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".page-tabs .tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const page = btn.dataset.page;
      document.getElementById("page-catalog").classList.toggle("hidden", page !== "catalog");
      document.getElementById("page-orders").classList.toggle("hidden", page !== "orders");
      if (page === "orders") loadOrders();
    });
  });
}

async function loadOrders() {
  const list = document.getElementById("order-list");
  const orders = await api("/api/orders");
  list.innerHTML = "";
  if (orders.length === 0) {
    list.innerHTML = '<div class="cart-empty">No orders yet -- check out from the catalog.</div>';
    return;
  }
  orders.forEach((order) => {
    const card = document.createElement("div");
    card.className = "order-card";
    const rows = order.items
      .map(
        (it) =>
          `<tr><td>${it.product_name}</td><td>× ${it.quantity}</td><td>₹${money(it.unit_price)}</td></tr>`
      )
      .join("");
    const paymentLine = order.payment
      ? `Payment: ${order.payment.method} — ${order.payment.status}`
      : "No payment attempt yet";
    card.innerHTML = `
      <div class="order-head">
        <strong>Order #${order.order_id}</strong>
        <span class="status-badge status-${order.status}">${order.status}</span>
      </div>
      <table>${rows}</table>
      <div class="order-head" style="margin-top:8px;">
        <span>Total</span><strong>₹${money(order.total_amount)}</strong>
      </div>
      <div class="payment-line">${paymentLine}</div>
    `;
    list.appendChild(card);
  });
}

// ---------------------------------------------------------------- wiring
document.addEventListener("DOMContentLoaded", () => {
  wireAuthTabs();
  wirePageTabs();
  document.getElementById("login-form").addEventListener("submit", handleLogin);
  document.getElementById("register-form").addEventListener("submit", handleRegister);
  document.getElementById("checkout-btn").addEventListener("click", handleCheckout);
  document.getElementById("pm-pay-btn").addEventListener("click", handlePay);
  document.getElementById("pm-close-btn").addEventListener("click", closePaymentModal);

  // If a session cookie is already valid (page refresh), skip the auth screen.
  api("/api/me")
    .then(onLoggedIn)
    .catch(() => {});
});
