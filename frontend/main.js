const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const receiptInput = document.getElementById("receipt");
const descriptionInput = document.getElementById("description");
const submitBtn = document.getElementById("submit");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const copyShareBtn = document.getElementById("copyShare");

let lastShareMessage = "";

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function formatMoney(value) {
  return `₹${Number(value).toLocaleString("en-IN")}`;
}

function renderList(el, items, emptyText = "None") {
  el.innerHTML = "";
  if (!items?.length) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    el.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = typeof item === "string" ? item : item.label || JSON.stringify(item);
    el.appendChild(li);
  }
}

function renderResults(data) {
  resultsEl.classList.remove("hidden");

  document.getElementById("grandTotal").textContent = formatMoney(data.grand_total);
  document.getElementById("paidBy").textContent = data.paid_by || "Not stated";

  const recon = data.reconciliation;
  const reconEl = document.getElementById("reconciliation");
  reconEl.innerHTML = `Sum: <strong>${formatMoney(recon.sum_of_person_totals)}</strong><br/>
    <span class="${recon.matches_bill ? "ok" : "bad"}">${recon.matches_bill ? "Matches bill ✓" : "Does not match ✗"}</span>`;

  const healthEl = document.getElementById("billHealth");
  if (data.bill_health) {
    const h = data.bill_health;
    const checks = (h.checks || []).map((c) => `${c.ok ? "✓" : "✗"} ${c.label}`).join("<br/>");
    healthEl.innerHTML = `<span class="${h.score >= 75 ? "ok" : "bad"}">${h.grade} · ${h.score}/100</span><br/><span class="muted">${checks}</span>`;
  } else {
    healthEl.textContent = "—";
  }

  const explainEl = document.getElementById("explanations");
  explainEl.innerHTML = "";
  if (data.explanations?.length) {
    for (const ex of data.explanations) {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${ex.name}</strong> — ${ex.summary}<br/><span class="muted">${ex.items}</span>`;
      explainEl.appendChild(li);
    }
  }

  const tbody = document.querySelector("#personTable tbody");
  tbody.innerHTML = "";
  for (const person of data.per_person) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${person.name}</td>
      <td>${person.items.join(", ")}</td>
      <td>${formatMoney(person.subtotal)}</td>
      <td>${formatMoney(person.service_share)}</td>
      <td>${formatMoney(person.tax_share)}</td>
      <td>${formatMoney(person.discount_share)}</td>
      <td><strong>${formatMoney(person.total)}</strong></td>
    `;
    tbody.appendChild(tr);
  }

  const settleEl = document.getElementById("settleUp");
  settleEl.innerHTML = "";
  if (!data.settle_up?.length) {
    const li = document.createElement("li");
    li.textContent = data.paid_by ? "No payments needed." : "Cannot compute settle-up without a payer.";
    settleEl.appendChild(li);
  } else {
    for (const entry of data.settle_up) {
      const li = document.createElement("li");
      li.textContent = `${entry.from} → ${entry.to}: ${formatMoney(entry.amount)}`;
      settleEl.appendChild(li);
    }
  }

  renderList(document.getElementById("assumptions"), data.assumptions);
  renderList(document.getElementById("flags"), data.flags);

  lastShareMessage = data.share_message || "";
}

function formatApiError(payload, status) {
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  if (status === 429) {
    return "API quota exceeded. Wait a minute or add GROQ_API_KEY (free at console.groq.com/keys).";
  }
  return payload.message || "Request failed";
}

async function splitBill() {
  const file = receiptInput.files?.[0];
  const description = descriptionInput.value.trim();
  if (!file) return setStatus("Please upload a receipt image.", true);
  if (!description) return setStatus("Please enter a description.", true);

  submitBtn.disabled = true;
  setStatus("Reading receipt and splitting bill…");

  try {
    const receipt_base64 = await fileToBase64(file);
    const response = await fetch(`${API_BASE}/split/enriched`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ receipt_base64, description }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(formatApiError(payload, response.status));
    renderResults(payload);
    setStatus("Done.");
  } catch (error) {
    setStatus(error.message || "Something went wrong.", true);
  } finally {
    submitBtn.disabled = false;
  }
}

copyShareBtn.addEventListener("click", async () => {
  if (!lastShareMessage) return setStatus("Nothing to copy yet.", true);
  try {
    await navigator.clipboard.writeText(lastShareMessage);
    setStatus("Copied to clipboard — paste in WhatsApp.");
  } catch {
    setStatus(lastShareMessage, false);
  }
});

submitBtn.addEventListener("click", splitBill);
