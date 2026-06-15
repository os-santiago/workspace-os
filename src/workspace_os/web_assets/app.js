const qs = (selector) => document.querySelector(selector);

const state = {
  conscienceCount: 0,
  learningCount: 0,
  contextCount: 0,
  handoffCount: 0,
  chatContextExpanded: false,
  conscienceExpanded: false,
  chatVerbose: false,
  latestConscience: null,
  latestSuggestedActions: [],
  latestNextAction: null,
  latestAnalysis: null,
  latestConscienceMetrics: null,
  latestConscienceRecommendation: null,
};

const CHAT_CONTEXT_STORAGE_KEY = "workspace-os.chat-context-expanded";
const CONSCIENCE_STORAGE_KEY = "workspace-os.conscience-expanded";
const CHAT_VERBOSE_STORAGE_KEY = "workspace-os.chat-verbose";

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
  qs("#conscienceIndicator").textContent = `OCE ${state.conscienceCount}`;
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
  if (data.root) {
    const rootRow = document.createElement("div");
    rootRow.className = "rail-item rail-root";
    rootRow.innerHTML = `
      <strong>Root</strong>
      <span>${escapeHtml(data.root)}</span>
      <small>workspace root</small>
    `;
    list.appendChild(rootRow);
  }
  if (!data.items || data.items.length === 0) {
    if (!data.root) {
      list.innerHTML = `<div class="rail-item muted">${emptyText}</div>`;
    } else {
      const emptyRow = document.createElement("div");
      emptyRow.className = "rail-item muted";
      emptyRow.textContent = emptyText;
      list.appendChild(emptyRow);
    }
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
    output.textContent = "Waiting for an OCE decision...";
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
  qs("#conscienceIndicator").textContent = `OCE ${state.conscienceCount}`;
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
    `Top missing context: ${summary.top_missing_context || "n/a"}`,
    `Next action: ${summary.recommended_next_action || "n/a"}`,
    "",
    "Decision counts:",
    ...renderKeyValueLines(summary.decision_counts),
    "",
    "Primary agents:",
    ...renderKeyValueLines(summary.primary_agent_counts),
    "",
    "Routing reasons:",
    ...renderKeyValueLines(summary.routing_reason_counts),
    "",
    "Missing context:",
    ...renderKeyValueLines(summary.missing_context_counts),
  ];
  output.textContent = lines.join("\n").trim();
};

const renderConscienceRecommendation = (data = null) => {
  const output = qs("#conscienceRecommendationOutput");
  if (!data || !data.ok) {
    output.textContent = data?.error || "Unable to load conscience recommendation.";
    return;
  }
  state.latestConscienceRecommendation = data.text || "";
  output.textContent = data.text || "No recommendation available.";
};

const renderNextAction = (data = null) => {
  const output = qs("#nextOutput");
  if (!data || !data.ok) {
    output.textContent = data?.error || "Unable to load next action.";
    return;
  }
  state.latestNextAction = data.text || "";
  output.textContent = data.text || "No next action available.";
};

const renderAnalysis = (data = null) => {
  const output = qs("#analysisOutput");
  if (!data || !data.ok) {
    output.textContent = data?.error || "Unable to load analysis.";
    return;
  }
  state.latestAnalysis = data.text || "";
  output.textContent = data.text || "No analysis available.";
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

const loadConscienceRecommendation = async () => {
  const data = await getJson("/api/conscience/recommend?limit=10");
  renderConscienceRecommendation(data);
};

const loadNextAction = async () => {
  const data = await getJson("/api/next");
  renderNextAction(data);
};

const loadAnalysis = async () => {
  const data = await getJson("/api/analysis");
  renderAnalysis(data);
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

const readChatVerbosePreference = () => {
  try {
    return window.localStorage.getItem(CHAT_VERBOSE_STORAGE_KEY) === "on";
  } catch {
    return false;
  }
};

const saveChatVerbosePreference = (enabled) => {
  try {
    window.localStorage.setItem(CHAT_VERBOSE_STORAGE_KEY, enabled ? "on" : "off");
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

const setChatVerbose = (enabled, persist = true) => {
  state.chatVerbose = enabled;
  const button = qs("#chatVerboseToggle");
  if (button) {
    button.textContent = state.chatVerbose ? "Verbose On" : "Verbose Off";
    button.setAttribute("aria-pressed", state.chatVerbose ? "true" : "false");
  }
  if (persist) {
    saveChatVerbosePreference(state.chatVerbose);
  }
};

const toggleChatVerbose = () => {
  setChatVerbose(!state.chatVerbose);
  appendMessage("system", `verbose=${state.chatVerbose ? "on" : "off"}`);
};

const handleLocalChatCommand = (message) => {
  const text = message.trim();
  if (!text.toLowerCase().startsWith("/verbose")) {
    return false;
  }
  const parts = text.split(/\s+/, 2);
  const arg = parts[1]?.toLowerCase() || "";
  if (!arg) {
    toggleChatVerbose();
    return true;
  }
  if (["on", "1", "true", "yes"].includes(arg)) {
    setChatVerbose(true);
    appendMessage("system", "verbose=on");
    return true;
  }
  if (["off", "0", "false", "no"].includes(arg)) {
    setChatVerbose(false);
    appendMessage("system", "verbose=off");
    return true;
  }
  appendMessage("system", "Usage: /verbose [on|off]");
  return true;
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
    if (handleLocalChatCommand(message)) {
      input.value = "";
      return;
    }
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
    last.querySelector("p").textContent = data.answer || data.reply;
    if (state.chatVerbose) {
      const verboseBlock = document.createElement("pre");
      verboseBlock.textContent = data.verbose_reply || [data.answer || data.reply || "", "", `Trace:`, data.trace || ""].join("\n");
      last.appendChild(verboseBlock);
    }
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
    }
    await loadNextAction();
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
  setChatVerbose(readChatVerbosePreference(), false);
  qs("#handoffDownload").addEventListener("click", () => {
    window.location.href = "/api/handoff.md?launch_limit=3";
  });
  qs("#chatContextToggle").addEventListener("click", toggleChatContext);
  qs("#conscienceToggle").addEventListener("click", toggleConscience);
  qs("#conscienceRefresh").addEventListener("click", () => {
    renderConscience(state.latestConscience);
  });
  qs("#conscienceRecommendRefresh").addEventListener("click", async () => {
    qs("#conscienceRecommendationOutput").textContent = "Loading OCE recommendation...";
    try {
      await loadConscienceRecommendation();
    } catch (error) {
      qs("#conscienceRecommendationOutput").textContent = error.message;
    }
  });
  qs("#conscienceMetricsRefresh").addEventListener("click", async () => {
    qs("#conscienceMetricsOutput").textContent = "Loading OCE metrics...";
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
  qs("#nextRefresh").addEventListener("click", async () => {
    qs("#nextOutput").textContent = "Loading next action...";
    try {
      await loadNextAction();
    } catch (error) {
      qs("#nextOutput").textContent = error.message;
    }
  });
  qs("#analysisRefresh").addEventListener("click", async () => {
    qs("#analysisOutput").textContent = "Loading analysis...";
    try {
      await loadAnalysis();
    } catch (error) {
      qs("#analysisOutput").textContent = error.message;
    }
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
  qs("#chatVerboseToggle").addEventListener("click", toggleChatVerbose);
  await loadSidebar();
  setChatContextExpanded(readChatContextPreference(), false);
  setConscienceExpanded(readConsciencePreference(), false);
  await loadContext();
  await loadAnalysis();
  await loadNextAction();
  await loadHandoff();
  await loadConscienceRecommendation();
  await loadConscienceMetrics();
  renderConscience(null);
  renderConscienceActions([]);
};

init().catch((error) => {
  appendMessage("system", "Startup error.", error.message);
});
