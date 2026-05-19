const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => Array.from(document.querySelectorAll(selector));

const state = {
  action: "validate",
};

const getJson = async (url) => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
};

const setOutput = (title, text) => {
  qs("#outputTitle").textContent = title;
  qs("#activeAction").textContent = state.action;
  qs("#mainOutput").textContent = text;
};

const renderStatus = async () => {
  const data = await getJson("/api/status");
  const dirtySources = data.sources.filter((source) => source.state !== "clean");
  qs("#sourceCount").textContent = data.sources.length;
  qs("#titleStatus").textContent = dirtySources.length === 0 ? "Ready" : "Needs attention";
  qs("#governanceState").textContent =
    dirtySources.length === 0 ? "Governance: stable" : `Governance: ${dirtySources.length} source(s) need review`;

  const list = qs("#sourceList");
  list.innerHTML = "";
  for (const source of data.sources) {
    const item = document.createElement("div");
    item.className = `source-item ${source.state === "clean" ? "ok" : "warn"}`;
    item.innerHTML = `
      <strong>${source.name}</strong>
      <span>${source.type} | ${source.branch || "n/a"} | ${source.state}</span>
    `;
    list.appendChild(item);
  }
};

const renderRoadmap = async () => {
  const data = await getJson("/api/roadmap");
  qs("#roadmapOutput").textContent = data.progress;
};

const runValidate = async () => {
  const data = await getJson("/api/validate?skip_housekeeping=true");
  const lines = data.results.map((result) => {
    const status = result.passed ? "PASS" : "FAIL";
    return `${status} ${result.name}\n  ${result.detail}`;
  });
  setOutput("Workspace validation", lines.join("\n\n"));
};

const runSearch = async (value) => {
  const query = value.trim() || "ADEV";
  const data = await getJson(`/api/search?query=${encodeURIComponent(query)}&max_results=10`);
  if (data.matches.length === 0) {
    setOutput("Knowledge search", `No matches found for "${query}".`);
    return;
  }
  const lines = data.matches.map((match) => `${match.source}:${match.path}:${match.line}\n  ${match.text}`);
  setOutput("Knowledge search", lines.join("\n\n"));
};

const runContext = async (value) => {
  const topic = value.trim() || "agent alignment";
  const data = await getJson(`/api/context?topic=${encodeURIComponent(topic)}&max_matches=6&max_doctrine_lines=16`);
  setOutput("Agent context", data.markdown);
};

const setAction = (action) => {
  state.action = action;
  for (const button of qsa(".action-button")) {
    button.classList.toggle("is-active", button.dataset.action === action);
  }

  const input = qs("#workspaceInput");
  const label = qs("#inputLabel");
  if (action === "validate") {
    label.textContent = "Input not required";
    input.value = "";
    input.placeholder = "Validation uses the configured sources";
  } else if (action === "search") {
    label.textContent = "Search term";
    input.value = input.value || "ADEV";
    input.placeholder = "Example: validation";
  } else {
    label.textContent = "Agent topic";
    input.value = input.value || "agent alignment";
    input.placeholder = "Example: software delivery";
  }
  qs("#activeAction").textContent = action;
};

const runActiveAction = async () => {
  const value = qs("#workspaceInput").value;
  qs("#mainOutput").textContent = "Running...";
  if (state.action === "validate") {
    await runValidate();
  } else if (state.action === "search") {
    await runSearch(value);
  } else {
    await runContext(value);
  }
};

const bindActions = () => {
  for (const button of qsa(".action-button")) {
    button.addEventListener("click", async () => {
      setAction(button.dataset.action);
      await runActiveAction();
    });
  }

  qs("#workspaceForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runActiveAction();
  });
};

const init = async () => {
  bindActions();
  setAction("validate");
  await Promise.all([renderStatus(), renderRoadmap()]);
  await runValidate();
};

init().catch((error) => {
  qs("#titleStatus").textContent = "Offline";
  setOutput("Startup error", error.message);
});
