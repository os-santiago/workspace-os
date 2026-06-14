const qs = (selector) => document.querySelector(selector);

const state = {
  conscienceCount: 0,
  learningCount: 0,
  contextCount: 0,
  handoffCount: 0,
  chatContextExpanded: false,
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

const scrollChatToBottom = () => {
  const stream = qs("#chatStream");
  stream.scrollTop = stream.scrollHeight;
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
  scrollChatToBottom();
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

const renderHandoff = (data) => {
  const output = qs("#handoffOutput");
  if (!data.ok) {
    output.textContent = data.error || "Unable to load handoff.";
    return;
  }
  state.handoffCount += 1;
  output.textContent = data.markdown || "No handoff available.";
};

const renderContext = (data, selector = "#contextOutput", expanded = false) => {
  const output = qs(selector);
  if (!data.ok) {
    output.textContent = data.error || "Unable to load context.";
    return;
  }
  const snapshot = data.snapshot;
  const lines = [
    `Reason: ${snapshot.reason}`,
    `Created: ${snapshot.created_at}`,
  ];
  if (expanded) {
    lines.push("", snapshot.markdown || snapshot.summary);
  } else {
    lines.push("", snapshot.summary);
  }
  output.textContent = lines.join("\n");
};

const renderContextSnapshot = (data) => {
  state.contextCount += 1;
  renderContext(data, "#contextOutput", true);
  renderContext(data, "#chatContextOutput", state.chatContextExpanded);
};

const loadSidebar = async () => {
  const [software, docs] = await Promise.all([
    getJson("/api/recent-software"),
    getJson("/api/recent-docs"),
  ]);
  renderRail("#softwareList", software, "No local projects found.");
  renderRail("#docsList", docs, "No Google Drive files found.");
};

const loadHandoff = async () => {
  const data = await getJson("/api/handoff?launch_limit=3");
  renderHandoff(data);
};

const loadContext = async () => {
  const data = await getJson("/api/context-snapshot");
  renderContextSnapshot(data);
};

const toggleChatContext = () => {
  state.chatContextExpanded = !state.chatContextExpanded;
  const section = qs(".chat-context");
  const button = qs("#chatContextToggle");
  section.classList.toggle("is-expanded", state.chatContextExpanded);
  section.classList.toggle("is-collapsed", !state.chatContextExpanded);
  button.textContent = state.chatContextExpanded ? "Collapse" : "Expand";
  loadContext().catch((error) => {
    qs("#chatContextOutput").textContent = error.message;
  });
};

const bindChat = () => {
  const input = qs("#chatInput");
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    qs("#chatForm").requestSubmit();
  });

  qs("#chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    appendMessage("user", message);
    input.value = "";
    appendMessage("system", "Thinking through conscience and learning engines...");
    const data = await postJson("/api/chat", { message });
    const last = qs("#chatStream").lastElementChild;
    if (!data.ok) {
      last.querySelector("p").textContent = data.error;
      scrollChatToBottom();
      return;
    }
    updateIndicators(Boolean(data.learning && data.learning.activated));
    last.querySelector("p").textContent = data.reply;
    if (data.context_snapshot) {
      renderContextSnapshot({
        ok: true,
        snapshot: data.context_snapshot,
      });
    }
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
    scrollChatToBottom();
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
  qs("#handoffDownload").addEventListener("click", () => {
    window.location.href = "/api/handoff.md?launch_limit=3";
  });
  qs("#chatContextToggle").addEventListener("click", toggleChatContext);
  qs("#chatContextRefresh").addEventListener("click", async () => {
    qs("#chatContextOutput").textContent = "Loading context...";
    try {
      await loadContext();
    } catch (error) {
      qs("#chatContextOutput").textContent = error.message;
    }
  });
  qs("#contextDownload").addEventListener("click", () => {
    window.location.href = "/api/context-snapshot.md";
  });
  qs("#handoffRefresh").addEventListener("click", async () => {
    qs("#handoffOutput").textContent = "Loading handoff...";
    try {
      await loadHandoff();
    } catch (error) {
      qs("#handoffOutput").textContent = error.message;
    }
  });
  qs("#contextRefresh").addEventListener("click", async () => {
    qs("#contextOutput").textContent = "Loading context...";
    try {
      await loadContext();
    } catch (error) {
      qs("#contextOutput").textContent = error.message;
    }
  });
  await loadSidebar();
  qs(".chat-context").classList.add("is-collapsed");
  await loadContext();
  await loadHandoff();
};

init().catch((error) => {
  appendMessage("system", "Startup error.", error.message);
});
