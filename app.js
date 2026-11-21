const form = document.querySelector("#analysis-form");
const fileInput = document.querySelector("#project-zip");
const dropZone = document.querySelector("#drop-zone");
const fileName = document.querySelector("#file-name");
const statusMessage = document.querySelector("#status-message");
const results = document.querySelector("#results");
const report = document.querySelector("#report");
const historyList = document.querySelector("#history-list");
const analyzeButton = document.querySelector("#analyze-button");

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response.");
  }
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.className = isError ? "status error" : "status";
}

function updateSelectedFile(file) {
  if (!file) {
    fileName.textContent = "Drop your ZIP file here, or browse";
    analyzeButton.disabled = true;
    return;
  }
  fileName.textContent = file.name;
  if (!file.name.toLowerCase().endsWith(".zip")) {
    setStatus("Choose a .zip archive.", true);
    analyzeButton.disabled = true;
  } else if (file.size > MAX_UPLOAD_BYTES) {
    setStatus("This archive exceeds the 25 MB upload limit.", true);
    analyzeButton.disabled = true;
  } else {
    setStatus(`${formatBytes(file.size)} selected.`);
    analyzeButton.disabled = false;
  }
}

function formatBytes(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function readinessClass(readiness) {
  if (readiness === "Ready to submit") return "ready";
  if (readiness && readiness.toLowerCase().includes("block")) return "blocked";
  if (readiness && readiness.toLowerCase().includes("fail")) return "blocked";
  return "pending";
}

function renderAnalysis(analysis) {
  results.hidden = false;
  report.replaceChildren();

  const header = element("div", "report-header");
  const titleRow = element("div", "report-title-row");
  const project = element("div");
  project.append(element("div", "report-project", analysis.project_name || "Project report"));
  project.append(element("div", "report-time", `Analyzed ${analysis.created_at}`));
  titleRow.append(project);
  titleRow.append(
    element(
      "span",
      `readiness-pill ${readinessClass(analysis.summary.submission_readiness)}`,
      analysis.summary.submission_readiness
    )
  );
  header.append(titleRow);

  const scoreSummary = element("div", "score-summary");
  scoreSummary.append(element("div", "score-circle", `${analysis.summary.quality_score}`));
  const scoreCopy = element("div", "score-copy");
  scoreCopy.append(element("strong", "", "Software quality score"));
  scoreCopy.append(element("p", "", analysis.summary.note));
  scoreSummary.append(scoreCopy);
  header.append(scoreSummary);
  header.append(
    element(
      "p",
      "summary-stats",
      `${analysis.summary.checks} checks · ${analysis.summary.errors} errors · ${analysis.summary.warnings} warnings · Tests: ${formatTestStatus(analysis.summary.test_status)}`
    )
  );

  const actions = element("div", "report-actions");
  actions.append(
    linkButton("Download JSON", `/api/analyses/${analysis.id}/export`, "primary-light")
  );
  actions.append(
    linkButton("Open HTML report", `/api/analyses/${analysis.id}/report`)
  );
  if (analysis.source_type === "upload") {
    const testButton = element("button", "small-button", "Run isolated pytest");
    testButton.type = "button";
    testButton.addEventListener("click", () => runTests(analysis.id, testButton));
    actions.append(testButton);
  }
  header.append(actions);
  report.append(header);

  renderProjectMetadata(analysis.project_metadata || {});
  renderAgentRuns(analysis.agent_runs || []);
  renderFindings(analysis);
  renderTraceability(analysis.traceability || []);
  if (analysis.test_result) renderTestResult(analysis.test_result);
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderProjectMetadata(metadata) {
  const section = element("section", "metadata-section");
  const heading = element("div", "subsection-heading");
  heading.append(element("h3", "", "Project intelligence"));
  heading.append(element("span", "count-badge", "detected locally"));
  section.append(heading);
  const grid = element("div", "metadata-grid");
  const items = [
    ["Languages", (metadata.languages || []).join(", ") || "None detected"],
    ["Frameworks", (metadata.frameworks || []).join(", ") || "None detected"],
    ["Entry points", (metadata.entry_points || []).join(", ") || "None detected"],
    ["Python files", String(metadata.python_files || 0)],
  ];
  for (const [label, value] of items) {
    const item = element("div", "metadata-item");
    item.append(element("span", "metadata-label", label));
    item.append(element("strong", "", value));
    grid.append(item);
  }
  section.append(grid);
  report.append(section);
}

function renderAgentRuns(runs) {
  const section = element("section", "agent-section");
  const heading = element("div", "subsection-heading");
  heading.append(element("h3", "", "Agent execution timeline"));
  heading.append(element("span", "count-badge", `${runs.length} stages`));
  section.append(heading);
  const list = element("ol", "agent-timeline");
  for (const run of runs) {
    const item = element("li", "agent-run");
    item.append(element("span", `agent-status ${run.status}`, run.status));
    const copy = element("div");
    copy.append(element("strong", "", run.name));
    copy.append(element("p", "agent-responsibility", run.responsibility));
    if (run.error) copy.append(element("p", "finding-path", run.error));
    item.append(copy);
    list.append(item);
  }
  section.append(list);
  report.append(section);
}

function linkButton(label, href, extraClass = "") {
  const link = element("a", `button-link ${extraClass}`, label);
  link.href = href;
  if (href.includes("/report")) {
    link.target = "_blank";
    link.rel = "noopener";
  }
  return link;
}

function renderFindings(analysis) {
  const section = element("section", "findings-section");
  const heading = element("div", "subsection-heading");
  heading.append(element("h3", "", "Automated review findings"));
  heading.append(element("span", "count-badge", `${analysis.findings.length} findings`));
  section.append(heading);

  if (!analysis.findings.length) {
    section.append(element("p", "report-empty", "No findings were reported by the configured checks."));
    report.append(section);
    return;
  }

  const list = element("ul", "finding-list");
  for (const finding of analysis.findings) {
    const item = element("li", "finding");
    const top = element("div", "finding-top");
    top.append(element("span", `severity ${finding.severity}`, finding.severity));
    top.append(element("span", "finding-title", finding.title));
    item.append(top);
    item.append(element("p", "finding-message", finding.message));
    if (finding.path) item.append(element("p", "finding-path", finding.path));
    list.append(item);
  }
  section.append(list);
  report.append(section);
}

function renderTraceability(matrix) {
  const section = element("section", "trace-section");
  const heading = element("div", "subsection-heading");
  heading.append(element("h3", "", "Requirements traceability"));
  heading.append(element("span", "count-badge", `${matrix.length} rows`));
  section.append(heading);
  if (!matrix.length) {
    section.append(element("p", "report-empty", "No dependency declarations were available to map."));
    report.append(section);
    return;
  }

  const wrapper = element("div", "table-wrap");
  const table = element("table", "trace-table");
  const header = element("thead");
  const headings = element("tr");
  for (const label of ["DEPENDENCY", "DECLARED IN", "PYTHON IMPORT EVIDENCE", "STATUS"]) {
    headings.append(element("th", "", label));
  }
  header.append(headings);
  table.append(header);
  const body = element("tbody");
  for (const row of matrix) {
    const tr = element("tr");
    tr.append(element("td", "", row.dependency));
    tr.append(element("td", "", row.declared_in));
    tr.append(element("td", "", (row.evidence || []).join(", ") || "—"));
    const status = element("td", `trace-status ${row.status.includes("possible") ? "warning" : ""}`, row.status);
    tr.append(status);
    body.append(tr);
  }
  table.append(body);
  wrapper.append(table);
  section.append(wrapper);
  report.append(section);
}

function formatTestStatus(status) {
  const labels = {
    not_run: "not run",
    passed: "passed",
    failed: "failed",
    timed_out: "timed out",
    unavailable: "runner unavailable",
    resource_limit: "resource limit",
    cleanup_failed: "cleanup issue",
    error: "runner error",
  };
  return labels[status] || status || "not run";
}

function renderTestResult(result) {
  const section = element("section", "test-section");
  const heading = element("div", "subsection-heading");
  heading.append(element("h3", "", `Isolated pytest: ${formatTestStatus(result.status)}`));
  section.append(heading);
  if (result.message) section.append(element("p", "test-note", result.message));
  section.append(
    element(
      "p",
      "test-note",
      "Tests ran in a network-disabled, read-only Docker container with memory, CPU, process, and time limits. Project code was not run inside Flask."
    )
  );
  if (result.output) section.append(element("pre", "test-output", result.output));
  if (result.truncated) {
    section.append(element("p", "test-note", "Output was truncated to protect application resources."));
  }
  report.append(section);
}

async function runTests(analysisId, button) {
  const confirmed = window.confirm(
    "Run uploaded project tests in Docker? Code will execute in a restricted container. Docker must be installed and the local pytest runner image must be built."
  );
  if (!confirmed) return;
  button.disabled = true;
  button.textContent = "Running isolated tests…";
  setStatus("Starting the restricted Docker test runner…");
  try {
    const result = await requestJson(`/api/analyses/${analysisId}/tests`, { method: "POST" });
    const refreshed = await requestJson(`/api/analyses/${analysisId}`);
    renderAnalysis(refreshed);
    setStatus(`Test runner status: ${formatTestStatus(result.status)}.`);
    await loadHistory();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Run isolated pytest";
  }
}

async function loadHistory() {
  try {
    const analyses = await requestJson("/api/analyses");
    historyList.replaceChildren();
    document.querySelector("#history-count").textContent =
      `${analyses.length} ${analyses.length === 1 ? "report" : "reports"}`;
    document.querySelector("#metric-total").textContent = analyses.length;
    const average = analyses.length
      ? Math.round(analyses.reduce((total, item) => total + item.readiness_score, 0) / analyses.length)
      : "—";
    document.querySelector("#metric-average").textContent = average;
    const latest = analyses[0];
    document.querySelector("#metric-findings").textContent = latest
      ? latest.summary.errors + latest.summary.warnings
      : "—";

    if (!analyses.length) {
      const empty = element("tr");
      empty.append(element("td", "empty-state", "No analyses yet. Upload a ZIP archive to get started."));
      empty.firstChild.colSpan = 5;
      historyList.append(empty);
      return;
    }

    for (const analysis of analyses) {
      const row = element("tr");
      row.append(element("td", "project-cell", analysis.project_name || "Project"));
      row.append(element("td", "", analysis.created_at));
      row.append(element("td", "score-cell", `${analysis.readiness_score} / 100`));
      row.append(
        element(
          "td",
          `history-status ${readinessClass(analysis.summary.submission_readiness)}`,
          analysis.summary.submission_readiness
        )
      );
      const actions = element("td");
      const actionGroup = element("div", "row-actions");
      const open = element("button", "row-action", "Open");
      open.type = "button";
      open.addEventListener("click", () => openAnalysis(analysis.id));
      const remove = element("button", "row-action delete", "Delete");
      remove.type = "button";
      remove.addEventListener("click", () => deleteAnalysis(analysis.id, analysis.project_name));
      actionGroup.append(open, remove);
      actions.append(actionGroup);
      row.append(actions);
      historyList.append(row);
    }
  } catch (error) {
    historyList.replaceChildren();
    const row = element("tr");
    const cell = element("td", "empty-state", `Could not load history: ${error.message}`);
    cell.colSpan = 5;
    row.append(cell);
    historyList.append(row);
  }
}

async function openAnalysis(analysisId) {
  try {
    renderAnalysis(await requestJson(`/api/analyses/${analysisId}`));
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function deleteAnalysis(analysisId, projectName) {
  if (!window.confirm(`Delete the saved report${projectName ? ` for "${projectName}"` : ""}? Uploaded project files will also be removed.`)) {
    return;
  }
  try {
    await requestJson(`/api/analyses/${analysisId}`, { method: "DELETE" });
    await loadHistory();
    setStatus("Saved report and uploaded project files deleted.");
    results.hidden = true;
  } catch (error) {
    setStatus(error.message, true);
  }
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => updateSelectedFile(fileInput.files[0]));

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
}
dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  updateSelectedFile(file);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file || !file.name.toLowerCase().endsWith(".zip") || file.size > MAX_UPLOAD_BYTES) {
    updateSelectedFile(file);
    return;
  }
  analyzeButton.disabled = true;
  analyzeButton.textContent = "Inspecting archive…";
  setStatus("Checking ZIP structure and analyzing project files locally.");
  try {
    const body = new FormData();
    body.append("project_zip", file);
    const analysis = await requestJson("/api/analyses/upload", { method: "POST", body });
    renderAnalysis(analysis);
    setStatus("Project review complete. No project code was executed.");
    form.reset();
    updateSelectedFile(null);
    await loadHistory();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    analyzeButton.textContent = "Analyze project →";
    analyzeButton.disabled = !fileInput.files[0];
  }
});

const demoButton = document.querySelector("#demo-button");
if (demoButton) {
  demoButton.addEventListener("click", async () => {
    demoButton.disabled = true;
    setStatus("Running the labeled demo project through all agent stages.");
    try {
      const analysis = await requestJson("/api/analyses/demo", { method: "POST" });
      renderAnalysis(analysis);
      setStatus("Demo review complete. The demo includes deliberately introduced issues.");
      await loadHistory();
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      demoButton.disabled = false;
    }
  });
}

loadHistory();
