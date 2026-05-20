const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => Array.from(document.querySelectorAll(selector));

const state = {
  action: "check",
  lastBrief: "",
  lastTask: "",
  lastConscience: null,
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
  setOutput("Check result", lines.join("\n\n"));
};

const runSearch = async (value) => {
  const query = value.trim() || "ADEV";
  const data = await getJson(`/api/search?query=${encodeURIComponent(query)}&max_results=10`);
  if (data.matches.length === 0) {
    setOutput("Ask result", `No matches found for "${query}".`);
    return;
  }
  const lines = data.matches.map((match) => `${match.source}:${match.path}:${match.line}\n  ${match.text}`);
  setOutput("Ask result", lines.join("\n\n"));
};

const runContext = async (value) => {
  const topic = value.trim() || "agent alignment";
  const data = await getJson(`/api/context?topic=${encodeURIComponent(topic)}&max_matches=6&max_doctrine_lines=16`);
  const header = [
    "DELEGATION BRIEF",
    "",
    `Task: ${topic}`,
    "Mode: prepare context only",
    "Execution: no agent command was launched from the browser",
    "",
  ].join("\n");
  state.lastTask = topic;
  state.lastBrief = `${header}${data.markdown}`;
  setOutput("Delegate brief", state.lastBrief);
  await previewConscience();
  qs("#launchPanel").classList.remove("is-hidden");
  qs("#launchResult").textContent = "Review the brief, select an agent, approve, then launch.";
};

const renderConscience = (conscience) => {
  state.lastConscience = conscience;
  qs("#conscienceResult").textContent = [
    `Decision: ${conscience.decision}`,
    `Risk: ${conscience.risk_level}`,
    `Strategy: ${conscience.response_strategy}`,
    `Rationale: ${conscience.rationale}`,
  ].join("\n");
};

const previewConscience = async () => {
  const data = await postJson("/api/conscience-preview", {
    task: state.lastTask,
    brief: state.lastBrief,
    destination: qs("#destinationSelect").value,
  });
  if (data.ok) renderConscience(data.conscience);
};

const setAction = (action) => {
  state.action = action;
  for (const button of qsa(".action-button")) {
    button.classList.toggle("is-active", button.dataset.action === action);
  }

  const input = qs("#workspaceInput");
  const label = qs("#inputLabel");
  const runButton = qs("#runButton");
  if (action === "check") {
    label.textContent = "Input not required";
    input.value = "";
    input.placeholder = "Validation uses the configured sources";
    runButton.textContent = "Check";
    qs("#launchPanel").classList.add("is-hidden");
  } else if (action === "ask") {
    label.textContent = "Question or keyword";
    input.value = input.value || "ADEV";
    input.placeholder = "Example: validation";
    runButton.textContent = "Ask";
    qs("#launchPanel").classList.add("is-hidden");
  } else {
    label.textContent = "Task to delegate";
    input.value = input.value || "agent alignment";
    input.placeholder = "Example: implement a safe capture workflow";
    runButton.textContent = "Prepare brief";
  }
  qs("#activeAction").textContent = action;
};

const bindLaunch = () => {
  qs("#destinationSelect").addEventListener("change", previewConscience);
  qs("#launchButton").addEventListener("click", async () => {
    const approved = qs("#approvalCheckbox").checked;
    const payload = {
      agent: qs("#agentSelect").value,
      destination: qs("#destinationSelect").value,
      task: state.lastTask,
      brief: state.lastBrief,
      approved,
    };
    qs("#launchResult").textContent = "Launching...";
    const data = await postJson("/api/delegate-launch", payload);
    if (!data.ok) {
      qs("#launchResult").textContent = data.error;
      if (data.conscience) renderConscience(data.conscience);
      return;
    }
    if (data.conscience) renderConscience(data.conscience);
    qs("#launchResult").textContent = `${data.agent} launched for ${data.destination}. PID ${data.pid}.`;
  });
};

const runActiveAction = async () => {
  const value = qs("#workspaceInput").value;
  qs("#mainOutput").textContent = "Running...";
  if (state.action === "check") {
    await runValidate();
  } else if (state.action === "ask") {
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
  bindLaunch();
  setAction("check");
  await Promise.all([renderStatus(), renderRoadmap()]);
  await runValidate();
};

init().catch((error) => {
  qs("#titleStatus").textContent = "Offline";
  setOutput("Startup error", error.message);
});
