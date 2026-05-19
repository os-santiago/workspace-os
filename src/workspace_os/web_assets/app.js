const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => Array.from(document.querySelectorAll(selector));

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

const sanitizeText = (value) =>
  value.replace(
    /(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|credential)(\s*[:=]\s*)([^\s,;]+)/gi,
    "$1$2[REDACTED]"
  );

const renderStatus = async () => {
  const data = await getJson("/api/status");
  const metrics = qs("#status");
  metrics.innerHTML = "";
  let dirty = 0;
  for (const source of data.sources) {
    if (source.state !== "clean") dirty += 1;
    const item = document.createElement("article");
    item.className = "metric";
    item.innerHTML = `
      <span class="eyebrow">${source.type}</span>
      <strong>${source.name}</strong>
      <span>${source.state} on ${source.branch || "n/a"}</span>
      <small class="muted">changes ${source.changes} | untracked ${source.untracked}</small>
    `;
    metrics.appendChild(item);
  }
  qs("#governanceMetric").textContent = `Governance: ${dirty === 0 ? "stable" : "attention"}`;
  qs("#knowledgeMetric").textContent = `Sources: ${data.sources.length}`;
  qs("#healthPanel").innerHTML = `
    <span class="panel-label">System health</span>
    <strong>${dirty === 0 ? "Stable" : "Attention"}</strong>
    <small>${dirty} source${dirty === 1 ? "" : "s"} need review</small>
  `;
};

const renderRoadmap = async () => {
  const data = await getJson("/api/roadmap");
  qs("#roadmapOutput").textContent = data.progress;
};

const renderValidation = async () => {
  const data = await getJson("/api/validate?skip_housekeeping=true");
  const container = qs("#validationResults");
  container.innerHTML = "";
  for (const result of data.results) {
    const item = document.createElement("div");
    item.className = `result-item ${result.passed ? "ok" : "fail"}`;
    item.textContent = `${result.passed ? "PASS" : "FAIL"} ${result.name}: ${result.detail}`;
    container.appendChild(item);
  }
};

const bindContexts = () => {
  for (const tab of qsa(".context-tab")) {
    tab.addEventListener("click", () => {
      const context = tab.dataset.context;
      for (const item of qsa(".context-tab")) item.classList.toggle("is-active", item === tab);
      for (const panel of qsa(".context-panel")) {
        panel.classList.toggle("is-active", panel.dataset.panel === context);
      }
    });
  }
};

const bindSearch = () => {
  qs("#searchForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = new FormData(event.target).get("query");
    const data = await getJson(`/api/search?query=${encodeURIComponent(query)}&max_results=8`);
    const container = qs("#searchResults");
    container.innerHTML = "";
    if (data.matches.length === 0) {
      container.innerHTML = '<div class="result-item">No matches found.</div>';
      return;
    }
    for (const match of data.matches) {
      const item = document.createElement("div");
      item.className = "result-item";
      item.textContent = `${match.source}:${match.path}:${match.line}: ${match.text}`;
      container.appendChild(item);
    }
  });
};

const bindContext = () => {
  qs("#contextForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const topic = new FormData(event.target).get("topic");
    const data = await getJson(`/api/context?topic=${encodeURIComponent(topic)}&max_matches=6&max_doctrine_lines=16`);
    qs("#contextOutput").textContent = data.markdown;
  });
};

const bindClassify = () => {
  qs("#classifyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = new FormData(event.target).get("value");
    const data = await getJson(`/api/classify?value=${encodeURIComponent(value)}`);
    qs("#classificationResult").textContent = `${data.target} | ${data.confidence} | ${data.reason}`;
  });
};

const bindCapture = () => {
  qs("#captureForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const data = await postJson("/api/capture-preview", {
      type: form.get("type"),
      title: form.get("title"),
      body: form.get("body"),
    });
    qs("#captureOutput").textContent = data.ok ? `${data.target}\n\n${data.content}` : data.error;
  });
};

const bindPromotion = () => {
  qs("#promoteForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const data = await postJson("/api/promote-preview", {
      target: form.get("target"),
      rule: form.get("rule"),
      evidence: form.get("evidence"),
    });
    qs("#promoteOutput").textContent = data.ok ? data.markdown : data.error;
  });
};

const bindSanitizer = () => {
  const input = qs("#sanitizeInput");
  const status = qs("#sanitizeStatus");
  const output = qs("#sanitizeOutput");
  const render = () => {
    const sanitized = sanitizeText(input.value);
    const changed = sanitized !== input.value;
    status.className = `result-item ${changed ? "fail" : "ok"}`;
    status.textContent = changed
      ? "Secret-like value detected and redacted in preview."
      : "No secret-like assignment detected.";
    output.textContent = sanitized;
  };
  input.addEventListener("input", render);
  render();
};

const init = async () => {
  bindContexts();
  bindSearch();
  bindContext();
  bindClassify();
  bindCapture();
  bindPromotion();
  bindSanitizer();
  qs("#validateButton").addEventListener("click", renderValidation);
  await Promise.all([renderStatus(), renderRoadmap(), renderValidation()]);
  qs("#searchForm").dispatchEvent(new Event("submit", { cancelable: true }));
  qs("#contextForm").dispatchEvent(new Event("submit", { cancelable: true }));
  qs("#classifyForm").dispatchEvent(new Event("submit", { cancelable: true }));
  qs("#captureForm").dispatchEvent(new Event("submit", { cancelable: true }));
  qs("#promoteForm").dispatchEvent(new Event("submit", { cancelable: true }));
};

init().catch((error) => {
  qs("#healthPanel").innerHTML = `
    <span class="panel-label">System health</span>
    <strong>Offline</strong>
    <small>${error.message}</small>
  `;
});
