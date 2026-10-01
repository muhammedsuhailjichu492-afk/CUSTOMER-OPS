const API = "/api";
const AGENTS = [
  "Intent Detection Agent",
  "Customer Data Agent",
  "Knowledge RAG Agent",
  "Investigation Agent",
  "Resolution Agent",
  "Escalation Agent",
];
const SAMPLES = [
  { label: "Order tracking", message: "Hi, where is my order ORD-10003? It's been more than a week.", email: "" },
  { label: "Refund", message: "I want to return the HMI panel from order ORD-10011 and get a refund.", email: "" },
  { label: "PLC error", message: "Our X200 PLC shows error E-101 and has stopped talking to the HMI. Please help.", email: "rahul@deccanauto.com" },
  { label: "VFD trip", message: "VFD keeps tripping with fault OC-201 during motor start. Production line down, urgent!", email: "kiran@bharatpumps.com" },
  { label: "Warranty", message: "Our servo motor has failed. Is it still under warranty? Need a replacement.", email: "sneha@coastalpack.in" },
  { label: "Billing", message: "We were charged twice for our last invoice, please correct it.", email: "sneha@coastalpack.in" },
  { label: "Complaint", message: "This is the third time I'm complaining. Worst support ever, unacceptable delay!", email: "arjun@kochimachines.in" },
  { label: "Unknown user", message: "Can you tell me the status of my shipment?", email: "" },
];

let currentFilter = "";
let currentTicket = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pretty = (s) => (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function toast(text) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = text;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

function renderPipeline(state = -1) {
  $("pipeline").innerHTML = AGENTS.map((a, i) => {
    const cls = i < state ? "done" : i === state ? "running" : "";
    return `<li class="${cls}"><span class="dot"></span>${a}</li>`;
  }).join("");
}

function renderSamples() {
  $("samples").innerHTML = SAMPLES.map((s, i) => `<button data-i="${i}">${s.label}</button>`).join("");
  $("samples").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      const s = SAMPLES[b.dataset.i];
      $("message").value = s.message;
      $("email").value = s.email;
      $("order").value = "";
    })
  );
}

async function loadHealth() {
  try {
    const h = await api("/health");
    const b = $("llmBadge");
    b.textContent = h.llm ? `LLM: Ollama · ${h.model}` : "LLM: template fallback";
    b.className = "badge " + (h.llm ? "on" : "off");
  } catch {
    $("llmBadge").textContent = "API offline";
  }
}

async function loadStats() {
  const s = await api("/stats");
  const items = [
    [s.total, "Total tickets"],
    [s.resolved, "Resolved"],
    [s.awaiting_approval, "Awaiting approval"],
    [s.escalated, "Escalated"],
    [s.resolution_rate + "%", "Resolution rate"],
    [s.customers, "Customers in CRM"],
  ];
  $("stats").innerHTML = items.map(([v, l]) => `<div class="stat"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
}

function renderFilters() {
  const opts = [["", "All"], ["Awaiting Approval", "Awaiting"], ["Escalated", "Escalated"], ["Resolved", "Resolved"]];
  $("filters").innerHTML = opts
    .map(([v, l]) => `<button data-v="${v}" class="${v === currentFilter ? "active" : ""}">${l}</button>`)
    .join("");
  $("filters").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      currentFilter = b.dataset.v;
      renderFilters();
      loadQueue();
    })
  );
}

function statusClass(s) {
  if (s === "Resolved") return "s-Resolved";
  if (s === "Escalated") return "s-Escalated";
  if (s === "Awaiting Approval") return "s-Awaiting";
  return "";
}

async function loadQueue() {
  const rows = await api("/tickets" + (currentFilter ? `?status=${encodeURIComponent(currentFilter)}` : ""));
  if (!rows.length) {
    $("queue").innerHTML = `<tr><td colspan="7" class="muted">No tickets yet.</td></tr>`;
    return;
  }
  $("queue").innerHTML = rows
    .map(
      (t) => `<tr data-id="${t.id}">
        <td class="mono">${t.ticket_number}</td>
        <td>${esc(t.customer)}</td>
        <td>${pretty(t.intent)}</td>
        <td><span class="chip p-${t.priority}">${t.priority}</span></td>
        <td>${pretty(t.proposed_action)}</td>
        <td><span class="chip ${statusClass(t.status)}">${t.status}</span></td>
        <td class="muted">${t.created_at}</td>
      </tr>`
    )
    .join("");
  $("queue").querySelectorAll("tr[data-id]").forEach((tr) =>
    tr.addEventListener("click", async () => {
      const t = await api("/tickets/" + tr.dataset.id);
      renderDetail(t, null);
      window.scrollTo({ top: 0, behavior: "smooth" });
    })
  );
}

async function loadCustomers() {
  const cs = await api("/customers");
  $("customers").innerHTML = cs
    .map(
      (c) => `<div class="cust">
        <b>${esc(c.name)} <span class="chip">${c.tier}</span></b>
        <div class="muted">${esc(c.company)}</div>
        <div class="e" data-email="${esc(c.email)}">${esc(c.email)}</div>
        <div class="o">${c.orders
          .map((o) => `<span data-order="${o.order_number}">${o.order_number}</span> · ${esc(o.product)} · ${o.status}`)
          .join("<br>")}</div>
      </div>`
    )
    .join("");
  $("customers").querySelectorAll("[data-email]").forEach((e) =>
    e.addEventListener("click", () => { $("email").value = e.dataset.email; toast("Email filled"); })
  );
  $("customers").querySelectorAll("[data-order]").forEach((e) =>
    e.addEventListener("click", () => { $("order").value = e.dataset.order; toast("Order filled"); })
  );
}

function findTrace(trace, name) {
  return trace ? (trace.find((t) => t.agent === name) || {}).output : null;
}

function renderDetail(t, trace) {
  currentTicket = t;
  const intentOut = findTrace(trace, "Intent Detection Agent");
  const dataOut = findTrace(trace, "Customer Data Agent");
  const kbOut = findTrace(trace, "Knowledge RAG Agent");
  const invOut = findTrace(trace, "Investigation Agent");

  const kbLog = (t.logs || []).find((l) => l.step === "Retrieved knowledge");
  const kb = kbOut || (kbLog ? JSON.parse(kbLog.detail) : []);

  const customerBox = dataOut && dataOut.found
    ? `<div class="kv">
        <span>Name</span><span>${esc(dataOut.customer.name)}</span>
        <span>Company</span><span>${esc(dataOut.customer.company)}</span>
        <span>Tier</span><span>${dataOut.customer.tier}</span>
        <span>Lifetime value</span><span>${money(dataOut.lifetime_value)}</span>
        ${dataOut.order ? `
        <span>Order</span><span>${dataOut.order.order_number}</span>
        <span>Product</span><span>${esc(dataOut.order.product)}</span>
        <span>Amount</span><span>${money(dataOut.order.amount)}</span>
        <span>Order status</span><span>${dataOut.order.status}</span>
        <span>Warranty left</span><span>${dataOut.order.warranty_months_left ?? "—"} months</span>` : ""}
      </div>`
    : `<div class="kv">
        <span>Customer</span><span>${esc(t.customer)}</span>
        <span>Company</span><span>${esc(t.company || "—")}</span>
        <span>Tier</span><span>${t.tier || "—"}</span>
        <span>Order</span><span>${t.order_number || "—"}</span>
      </div>`;

  const entities = intentOut && Object.keys(intentOut.entities).length
    ? `<div class="chips">${Object.entries(intentOut.entities).map(([k, v]) => `<span class="chip">${k}: ${esc(v)}</span>`).join("")}</div>`
    : "";

  const checks = invOut && invOut.checks.length
    ? `<div class="chips">${invOut.checks.map((c) => `<span class="chip ${c.passed ? "s-Resolved" : "s-Escalated"}">${c.passed ? "✓" : "✗"} ${esc(c.check)}</span>`).join("")}</div>`
    : "";

  const canReview = t.status === "Awaiting Approval" || t.status === "Escalated";

  $("detail").innerHTML = `
    <div class="detail-head">
      <div>
        <div class="tn">${t.ticket_number}</div>
        <h2 style="margin:4px 0 0">${pretty(t.intent)} ${t.confidence != null ? `<span class="muted">(${Math.round(t.confidence * 100)}% confidence)</span>` : ""}</h2>
      </div>
      <span class="chip ${statusClass(t.status)}" style="font-size:13px">${t.status}${t.escalated_to ? " → " + esc(t.escalated_to) : ""}</span>
    </div>
    <div class="chips">
      <span class="chip p-${t.priority}">Priority: ${t.priority}</span>
      <span class="chip">Sentiment: ${t.sentiment}</span>
      <span class="chip">Action: ${pretty(t.proposed_action)}</span>
      ${t.action_amount ? `<span class="chip">Amount: ${money(t.action_amount)}</span>` : ""}
    </div>
    ${entities}
    <div class="msg">${esc(t.message)}</div>

    <div class="cols">
      <div class="box"><h4>Customer & Order (CRM / SQL)</h4>${customerBox}</div>
      <div class="box"><h4>Knowledge Retrieved (RAG)</h4>
        ${kb.length ? kb.map((k) => `<div class="kb"><span class="score">${k.score}</span><div class="src">${esc(k.source)}</div>${esc(k.section)}</div>`).join("") : '<span class="muted">No relevant articles.</span>'}
      </div>
    </div>

    <div class="cols section">
      <div class="box"><h4>Investigation Findings</h4>
        ${invOut ? `<div class="muted" style="margin-bottom:8px">Root cause: <b style="color:var(--text)">${esc(invOut.root_cause)}</b></div>` : ""}
        ${checks}
        <ul>${(t.findings || []).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      </div>
      <div class="box"><h4>Resolution Workflow</h4>
        <ol style="margin:0;padding-left:18px">${(t.resolution_steps || []).map((s) => `<li style="margin-bottom:6px">${esc(s)}</li>`).join("")}</ol>
      </div>
    </div>

    ${t.escalation_reason ? `<div class="box esc section"><h4>Escalation</h4>${esc(t.escalation_reason)}</div>` : ""}

    <div class="box reply section">
      <h4>Customer Reply Draft</h4>
      <textarea id="replyBox">${esc(t.reply_draft)}</textarea>
      <div class="actions">
        <button id="saveReply">Save reply</button>
        <button id="copyReply">Copy</button>
        ${canReview ? `<button class="ok" id="approveBtn">Approve & Execute</button><button class="bad" id="rejectBtn">Reject</button>` : ""}
      </div>
    </div>

    <div class="box section"><h4>Agent Audit Log</h4>
      <div class="logs">${(t.logs || []).map((l) => `<div><span class="muted">${l.at}</span> <span class="a">${esc(l.agent)}</span> · ${esc(l.step)}</div>`).join("")}</div>
    </div>
  `;

  $("saveReply").onclick = async () => {
    const updated = await api(`/tickets/${t.id}/reply`, { method: "PUT", body: JSON.stringify({ reply_draft: $("replyBox").value }) });
    currentTicket = updated;
    toast("Reply saved");
  };
  $("copyReply").onclick = () => { navigator.clipboard.writeText($("replyBox").value); toast("Copied"); };
  if (canReview) {
    $("approveBtn").onclick = () => review("approve", trace);
    $("rejectBtn").onclick = () => review("reject", trace);
  }
}

async function review(kind, trace) {
  const note = kind === "reject" ? prompt("Reason for rejection?") || "" : "";
  const t = await api(`/tickets/${currentTicket.id}/${kind}`, {
    method: "POST",
    body: JSON.stringify({ reviewer: "Support Lead", note }),
  });
  renderDetail(t, trace);
  toast(kind === "approve" ? "Approved & executed" : "Rejected");
  refreshAll();
}

async function submitTicket() {
  const message = $("message").value.trim();
  if (!message) return toast("Enter a message");
  $("submitBtn").disabled = true;
  $("submitBtn").textContent = "Agents working…";

  let step = 0;
  renderPipeline(0);
  const timer = setInterval(() => { step = Math.min(step + 1, AGENTS.length - 1); renderPipeline(step); }, 350);

  try {
    const res = await api("/tickets", {
      method: "POST",
      body: JSON.stringify({ message, email: $("email").value || null, order_number: $("order").value || null }),
    });
    clearInterval(timer);
    renderPipeline(AGENTS.length);
    renderDetail(res.ticket, res.trace);
    refreshAll();
  } catch (e) {
    clearInterval(timer);
    renderPipeline(-1);
    toast("Error: " + e.message);
  } finally {
    $("submitBtn").disabled = false;
    $("submitBtn").textContent = "Run Agents";
  }
}

function refreshAll() {
  loadStats();
  loadQueue();
  loadCustomers();
}

$("submitBtn").addEventListener("click", submitTicket);
renderSamples();
renderPipeline();
renderFilters();
loadHealth();
refreshAll();
