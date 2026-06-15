const qs = (selector) => document.querySelector(selector);

const state = {
  conscienceCount: 0,
  learningCount: 0,
  contextCount: 0,
  handoffCount: 0,
  chatContextExpanded: false,
  conscienceExpanded: false,
  latestConscience: null,
  latestSuggestedActions: [],
  latestConscienceMetrics: null,
};

const CHAT_CONTEXT_STORAGE_KEY = "workspace-os.chat-context-expanded";
const CONSCIENCE_STORAGE_KEY = "workspace-os.conscience-expanded";

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

const launchSuggestedAction = async (action, button) => {
  button.disabled = true;
  button.textContent = `Launching ${action.agent}...`;
  try {
    const result = await postJson("/api/delegate-launch", {
      agent: action.agent,
      destination: "software",
      task: action.task,
      brief: action.brief,
      approved: true,
    });
    appendMessage(
      "system",
      `${action.agent} launch complete.`,
      [
        `pid=${result.pid}`,
        `decision=${result.conscience?.decision || "n/a"}`,
        `risk=${result.conscience?.risk_level || "n/a"}`,
      ].join("\n"),
    );
  } catch (error) {
    appendMessage("system", `${action.agent} launch failed.`, error.message);
  } finally {
    button.disabled = false;
    button.textContent = `Launch ${action.agent}`;
  }
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

const renderConscience = (data = null) => {
  const output = qs("#conscienceOutput");
  const actions = qs("#conscienceActions");
  if (!data) {
    output.textContent = "Waiting for a conscience decision...";
    actions.innerHTML = "";
    return;
  }
  state.latestConscience = data;
  const lines = [
    `Decision: ${data.decision || "n/a"}`,
    `Risk: ${data.risk_level || "n/a"}`,
    `Strategy: ${data.response_strategy || "n/a"}`,
    `Primary: ${data.primary_agent || "n/a"}`,
    `Secondary: ${data.secondary_agent || "n/a"}`,
    `Policy refs: ${(data.policy_refs || []).join(", ") || "n/a"}`,
    "",
    `Context:`,
    `- intent=${data.context?.user_intent || "n/a"}`,
    `- domain=${data.context?.domain || "n/a"}`,
    `- reversibility=${data.context?.reversibility || "n/a"}`,
    `- salience=${data.context?.moral_salience || "n/a"}`,
  ];
  if (state.conscienceExpanded) {
    lines.push(
      "",
      "Applicable norms:",
      ...((data.applicable_norms || []).map((norm) => `- ${norm}`)),
      "",
      "Missing context:",
      ...((data.missing_context || []).map((value) => `- ${value}`)),
    );
  }
  output.textContent = lines.join("\n");
  qs("#conscienceToggle").textContent = state.conscienceExpanded ? "Collapse" : "Expand";
  qs(".conscience-section").classList.toggle("is-collapsed", !state.conscienceExpanded);
  qs(".conscience-section").classList.toggle("is-expanded", state.conscienceExpanded);
  qs("#conscienceIndicator").textContent = `Conscience ${state.conscienceCount}`;
  renderConscienceActions();
};

const renderConscienceActions = (actions = state.latestSuggestedActions) => {
  const container = qs("#conscienceActions");
  container.innerHTML = "";
  if (!actions || actions.length === 0) {
    return;
  }
  const header = document.createElement("p");
  header.textContent = "Suggested routes:";
  container.appendChild(header);
  for (const action of actions) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `Launch ${action.agent}`;
    button.addEventListener("click", () => {
      launchSuggestedAction(action, button).catch((error) => {
        appendMessage("system", `${action.agent} launch failed.`, error.message);
      });
    });
    container.appendChild(button);
  }
};

const renderConscienceMetrics = (data = null) => {
  const output = qs("#conscienceMetricsOutput");
  if (!data || !data.ok) {
    output.textContent = data?.error || "Unable to load conscience metrics.";
    return;
  }
  state.latestConscienceMetrics = data.report || null;
  const summary = data.report?.summary || {};
  const lines = [
    `Total: ${summary.total || 0}`,
    `Redirect rate: ${formatPercent(summary.redirect_rate)}`,
    `Allow rate: ${formatPercent(summary.allow_rate)}`,
    `Limit rate: ${formatPercent(summary.limit_rate)}`,
    `Refusal rate: ${formatPercent(summary.refusal_rate)}`,
    "",
    "Decision counts:",
    ...renderKeyValueLines(summary.decision_counts),
    "",
    "Primary agents:",
    ...renderKeyValueLines(summary.primary_agent_counts),
    "",
    "Routing reasons:",
    ...renderKeyValueLines(summary.routing_reason_counts),
  ];
  output.textContent = lines.join("\n").trim();
};

const renderKeyValueLines = (value) => {
  if (!value || typeof value !== "object") return ["- n/a=0"];
  const entries = Object.entries(value);
  if (entries.length === 0) return ["- n/a=0"];
  return entries.map(([key, count]) => `- ${key}=${count}`);
};

const formatPercent = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0%";
  return `${Math.round(number * 100)}%`;
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

const loadConscienceMetrics = async () => {
  const data = await getJson("/api/conscience?limit=10");
  renderConscienceMetrics(data);
};

const loadContext = async () => {
  const data = await getJson("/api/context-snapshot");
  renderContextSnapshot(data);
};

const readChatContextPreference = () => {
  try {
    return window.localStorage.getItem(CHAT_CONTEXT_STORAGE_KEY) === "expanded";
  } catch {
    return false;
  }
};

const readConsciencePreference = () => {
  try {
    return window.localStorage.getItem(CONSCIENCE_STORAGE_KEY) === "expanded";
  } catch {
    return false;
  }
};

const saveChatContextPreference = (expanded) => {
  try {
    window.localStorage.setItem(CHAT_CONTEXT_STORAGE_KEY, expanded ? "expanded" : "collapsed");
  } catch {
    return;
  }
};

const saveConsciencePreference = (expanded) => {
  try {
    window.localStorage.setItem(CONSCIENCE_STORAGE_KEY, expanded ? "expanded" : "collapsed");
  } catch {
    return;
  }
};

const setChatContextExpanded = (expanded, persist = true) => {
  state.chatContextExpanded = expanded;
  const section = qs(".chat-context");
  const button = qs("#chatContextToggle");
  section.classList.toggle("is-expanded", state.chatContextExpanded);
  section.classList.toggle("is-collapsed", !state.chatContextExpanded);
  button.textContent = state.chatContextExpanded ? "Collapse" : "Expand";
  if (persist) {
    saveChatContextPreference(state.chatContextExpanded);
  }
};

const toggleChatContext = () => {
  setChatContextExpanded(!state.chatContextExpanded);
  loadContext().catch((error) => {
    qs("#chatContextOutput").textContent = error.message;
  });
};

const setConscienceExpanded = (expanded, persist = true) => {
  state.conscienceExpanded = expanded;
  const section = qs(".conscience-section");
  const button = qs("#conscienceToggle");
  section.classList.toggle("is-expanded", state.conscienceExpanded);
  section.classList.toggle("is-collapsed", !state.conscienceExpanded);
  button.textContent = state.conscienceExpanded ? "Collapse" : "Expand";
  if (persist) {
    saveConsciencePreference(state.conscienceExpanded);
  }
  renderConscience(state.latestConscience);
};

const toggleConscience = () => {
  setConscienceExpanded(!state.conscienceExpanded);
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
      renderConscience(data.conscience);
      state.latestSuggestedActions = data.suggested_actions || [];
      renderConscienceActions();
      const details = [
        `Decision: ${data.conscience.decision}`,
        `Risk: ${data.conscience.risk_level}`,
        `Strategy: ${data.conscience.response_strategy}`,
      ].join("\n");
      const detailBlock = document.createElement("pre");
      detailBlock.textContent = details;
      last.appendChild(detailBlock);
    }
    if (data.suggested_actions && data.suggested_actions.length > 0) {
      state.latestSuggestedActions = data.suggested_actions;
      renderConscienceActions();
      const actions = document.createElement("div");
      actions.className = "suggested-actions";
      const header = document.createElement("p");
      header.textContent = "Suggested routes:";
      actions.appendChild(header);
      for (const action of data.suggested_actions) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `Launch ${action.agent}`;
        button.addEventListener("click", () => {
          launchSuggestedAction(action, button).catch((error) => {
            appendMessage("system", `${action.agent} launch failed.`, error.message);
          });
        });
        actions.appendChild(button);
      }
      last.appendChild(actions);
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
  qs("#conscienceToggle").addEventListener("click", toggleConscience);
  qs("#conscienceRefresh").addEventListener("click", () => {
    renderConscience(state.latestConscience);
  });
  qs("#conscienceMetricsRefresh").addEventListener("click", async () => {
    qs("#conscienceMetricsOutput").textContent = "Loading conscience metrics...";
    try {
      await loadConscienceMetrics();
    } catch (error) {
      qs("#conscienceMetricsOutput").textContent = error.message;
    }
  });
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
  setChatContextExpanded(readChatContextPreference(), false);
  setConscienceExpanded(readConsciencePreference(), false);
  await loadContext();
  await loadHandoff();
  await loadConscienceMetrics();
  renderConscience(null);
  renderConscienceActions([]);
};

init().catch((error) => {
  appendMessage("system", "Startup error.", error.message);
});
