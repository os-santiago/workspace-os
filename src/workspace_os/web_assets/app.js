const qs = (selector) => document.querySelector(selector);

const state = {
  conscienceCount: 0,
  learningCount: 0,
};

const getJson = async (url) => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
};

const postJson = async (url, payload) => {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
};

const updateIndicators = (learningActivated = false) => {
  state.conscienceCount += 1;
  if (learningActivated) state.learningCount += 1;
  qs("#conscienceIndicator").textContent = `Conscience ${state.conscienceCount}`;
  qs("#learningIndicator").textContent = `Learning ${state.learningCount}`;
};

const appendMessage = (role, text, details = "") => {
  const item = document.createElement("article");
  item.className = `message ${role}-message`;
  item.innerHTML = `
    <strong>${role === "user" ? "You" : "Workspace OS"}</strong>
    <p>${escapeHtml(text)}</p>
    ${details ? `<pre>${escapeHtml(details)}</pre>` : ""}
  `;
  qs("#chatStream").appendChild(item);
  item.scrollIntoView({ block: "end" });
};

const renderRail = (selector, data, emptyText) => {
  const list = qs(selector);
  list.innerHTML = "";
  if (!data.items || data.items.length === 0) {
    list.innerHTML = `<div class="rail-item muted">${emptyText}</div>`;
    return;
  }
  for (const item of data.items) {
    const row = document.createElement("div");
    row.className = "rail-item";
    row.innerHTML = `
      <strong>${escapeHtml(item.name)}</strong>
      <span>${escapeHtml(item.updated || "unknown")}</span>
      <small>${escapeHtml(item.relative_path || item.name)}</small>
    `;
    list.appendChild(row);
  }
};

const loadSidebar = async () => {
  const [software, docs] = await Promise.all([
    getJson("/api/recent-software"),
    getJson("/api/recent-docs"),
  ]);
  renderRail("#softwareList", software, "No local projects found.");
  renderRail("#docsList", docs, "No Google Drive files found.");
};

const bindChat = () => {
  qs("#chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = qs("#chatInput");
    const message = input.value.trim();
    if (!message) return;
    appendMessage("user", message);
    input.value = "";
    appendMessage("system", "Thinking through conscience and learning engines...");
    const data = await postJson("/api/chat", { message });
    const last = qs("#chatStream").lastElementChild;
    if (!data.ok) {
      last.querySelector("p").textContent = data.error;
      return;
    }
    updateIndicators(Boolean(data.learning && data.learning.activated));
    last.querySelector("p").textContent = data.reply;
    if (data.conscience) {
      const details = [
        `Decision: ${data.conscience.decision}`,
        `Risk: ${data.conscience.risk_level}`,
        `Strategy: ${data.conscience.response_strategy}`,
      ].join("\n");
      const detailBlock = document.createElement("pre");
      detailBlock.textContent = details;
      last.appendChild(detailBlock);
    }
  });
};

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const init = async () => {
  bindChat();
  await loadSidebar();
};

init().catch((error) => {
  appendMessage("system", "Startup error.", error.message);
});
