/* Static faculty console. All approvals and audit entries stay in this browser. */
(() => {
  const $ = (selector) => document.querySelector(selector);
  const stateKey = "acadza-review-state-v1";
  const safeTags = new Set(("article section div p span strong em b i br hr h1 h2 h3 h4 ul ol li table thead tbody tr th td sub sup mark math mi mn mo mrow mfrac msup msub mover munder munderover mtext mspace mstyle mtable mtr mtd msqrt mfenced semantics annotation mroot mpadded menclose mphantom").split(" "));
  const safeMathAttrs = new Set(("xmlns display mathvariant mathsize mathcolor stretchy fence form linebreak width columnalign rowalign rowspan columnspan notation").split(" "));
  let cases = [];
  let selected = 0;
  let activeFilter = "all";
  let searchText = "";
  let toastTimer;
  let state = loadState();

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(stateKey)) || {};
      return { actions: saved.actions && typeof saved.actions === "object" ? saved.actions : {}, audit: saved.audit && typeof saved.audit === "object" ? saved.audit : {} };
    }
    catch { return { actions: {}, audit: {} }; }
  }
  function saveState() { localStorage.setItem(stateKey, JSON.stringify(state)); }
  function toast(message) {
    const node = $("#toast"); node.textContent = message; node.classList.add("visible");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove("visible"), 2600);
  }
  async function fetchJson(path, fallback) {
    try { const response = await fetch(path); if (!response.ok) return fallback; return await response.json(); }
    catch { return fallback; }
  }

  function sanitize(html) {
    const parsed = new DOMParser().parseFromString(`<body>${html || ""}</body>`, "text/html");
    const clone = (node) => {
      if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.nodeValue || "");
      if (node.nodeType !== Node.ELEMENT_NODE) return document.createDocumentFragment();
      const tag = node.localName.toLowerCase();
      if (["script", "style", "iframe", "object", "svg", "form"].includes(tag)) return document.createDocumentFragment();
      if (!safeTags.has(tag)) {
        const fragment = document.createDocumentFragment();
        for (const child of node.childNodes) fragment.append(clone(child));
        return fragment;
      }
      const mathNamespace = "http://www.w3.org/1998/Math/MathML";
      const inMath = node.namespaceURI === mathNamespace || tag === "math";
      const element = inMath ? document.createElementNS(mathNamespace, tag) : document.createElement(tag);
      for (const attr of node.attributes) {
        const name = attr.name.toLowerCase();
        const allowed = tag === "math" || tag.startsWith("m") ? safeMathAttrs.has(name) : false;
        if (allowed) element.setAttribute(name, attr.value);
      }
      for (const child of node.childNodes) element.append(clone(child));
      return element;
    };
    const fragment = document.createDocumentFragment();
    for (const child of parsed.body.childNodes) fragment.append(clone(child));
    return fragment;
  }
  function renderHtml(element, source) { element.replaceChildren(sanitize(source)); }
  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }
  function getPayload(item) { return item.question[item.question.questionType] || {}; }
  function displayAnswer(answer) { return Array.isArray(answer) ? answer.join(", ") : String(answer ?? "Not set"); }
  function caseAction(item) { return (state.actions || {})[item.id] || {}; }
  function resultRoute(item) { return caseAction(item).route || item.result?.route || "needs"; }
  function isResolved(item) { return Boolean(caseAction(item).action); }

  function makeCases(questions, reports, results, internal) {
    const resultByReport = new Map(results.map(row => [row.reportId, row]));
    const internalByQuestion = new Map(internal.map(row => [row.questionId, row]));
    const grouped = new Map();
    for (const report of reports) {
      if (!grouped.has(report.questionId)) grouped.set(report.questionId, []);
      grouped.get(report.questionId).push(report);
    }
    return [...grouped.entries()].map(([id, group]) => {
      const question = questions.find(item => item._id === id);
      const rows = group.map(report => resultByReport.get(report.reportId)).filter(Boolean);
      return {
        id, question, reports: group, result: rows[0] || null,
        internal: internalByQuestion.get(id) || null,
        resultRows: rows,
        title: question?.chapter || "Question",
        subject: question?.subject || "Unknown subject",
      };
    }).filter(item => item.question);
  }
  function urgency(item) {
    const result = item.result;
    if (!result) return item.reports.length * 110 + (item.internal?.deterministic_findings?.length || 0) * 40;
    if (result.verdict === "defect" && result.repair === "answer_key") return 100000 + item.reports.length * 100;
    if (result.verdict === "defect") return 50000 + item.reports.length * 100 + (result.repair === "diagram" || result.repair === "wrong_question" ? 600 : 0);
    const penalty = { display_issue: 400, app_issue: 350, language_mode: 250, already_fixed: 100, no_error: -2000, not_actionable: -3000 }[result.verdict] ?? 0;
    const severity = item.internal?.deterministic_findings?.some(f => f.severity === "high") ? 500 : 0;
    return penalty + severity + item.reports.length * 100;
  }
  function visibleCases() {
    return cases.filter(item => {
      const action = caseAction(item); const route = resultRoute(item);
      if (activeFilter === "needs" && (action.action || route !== "faculty_review" && route !== "needs")) return false;
      if (activeFilter === "auto" && route !== "auto_apply") return false;
      if (activeFilter === "resolved" && !action.action) return false;
      if (searchText) {
        const query = `${item.id} ${item.title} ${item.subject} ${item.reports.map(r => `${r.reportId} ${r.comment}`).join(" ")}`.toLowerCase();
        if (!query.includes(searchText)) return false;
      }
      return true;
    }).sort((a, b) => urgency(b) - urgency(a) || b.reports.length - a.reports.length || a.id.localeCompare(b.id));
  }
  function renderQueue() {
    const list = visibleCases();
    $("#queue").replaceChildren();
    $("#queue-count").textContent = String(list.length);
    $("#filter-all").textContent = String(cases.length);
    $("#filter-needs").textContent = String(cases.filter(item => ["faculty_review", "needs"].includes(resultRoute(item)) && !isResolved(item)).length);
    $("#filter-auto").textContent = String(cases.filter(item => resultRoute(item) === "auto_apply").length);
    $("#filter-resolved").textContent = String(cases.filter(isResolved).length);
    for (const [index, item] of list.entries()) {
      const button = document.createElement("button");
      button.type = "button"; button.className = `case-card${cases[selected]?.id === item.id ? " selected" : ""}`;
      button.setAttribute("aria-current", cases[selected]?.id === item.id ? "true" : "false");
      const status = caseAction(item).action || (item.result ? item.result.verdict.replaceAll("_", " ") : "analysis pending");
      button.innerHTML = `<span class="case-card-top"><span class="case-subject">${escapeHtml(item.subject)}</span><span class="case-reporter-count">${item.reports.length} report${item.reports.length === 1 ? "" : "s"}</span></span><strong>${escapeHtml(item.title)}</strong><span class="case-card-bottom"><span class="queue-status ${item.result ? "has-result" : "pending-status"}">${escapeHtml(status)}</span><span class="case-card-arrow" aria-hidden="true">↗</span></span>`;
      button.addEventListener("click", () => { selected = cases.findIndex(c => c.id === item.id); renderSelected(); renderQueue(); });
      $("#queue").append(button);
    }
    if (!list.length) $("#queue").innerHTML = '<p class="empty-note queue-empty">No questions match this filter.</p>';
    const currentVisible = list.findIndex(item => item.id === cases[selected]?.id);
    $("#case-position").textContent = list.length ? `${Math.max(0, currentVisible) + 1} / ${list.length}` : "0 / 0";
  }
  function addAudit(item, action, reason = "") {
    const row = { who: $("#reviewer").value.trim() || "Faculty", what: action, reason, when: new Date().toISOString() };
    (state.audit[item.id] ||= []).push(row); saveState(); renderAudit(item);
  }
  function renderAudit(item) {
    const list = $("#audit-list"); list.replaceChildren();
    for (const row of [...(state.audit[item.id] || [])].reverse()) {
      const li = document.createElement("li");
      const date = new Date(row.when).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
      li.innerHTML = `<strong>${escapeHtml(row.what.replaceAll("_", " "))}</strong><span>${escapeHtml(row.who)} · ${escapeHtml(date)}</span>${row.reason ? `<p>${escapeHtml(row.reason)}</p>` : ""}`;
      list.append(li);
    }
    if (!list.children.length) list.innerHTML = '<li class="empty-audit">No decisions recorded yet.</li>';
  }
  function diffHtml(source, needle, className) {
    const fragment = sanitize(source);
    if (!needle) return fragment;
    const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT, {
      acceptNode(node) { return node.parentElement?.closest("math") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
    });
    const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const at = node.nodeValue.indexOf(needle); if (at < 0) continue;
      const range = document.createRange(); range.setStart(node, at); range.setEnd(node, at + needle.length);
      const mark = document.createElement("mark"); mark.className = className; range.surroundContents(mark); break;
    }
    return fragment;
  }
  function currentEdit(item) { return caseAction(item).edit || item.result?.edit || null; }
  function renderDiff(item) {
    const container = $("#diff-content"); container.replaceChildren();
    const edit = currentEdit(item); const data = getPayload(item);
    if (!edit) {
      $("#diff-state").textContent = "No edit proposed";
      container.innerHTML = '<p class="empty-note">There is no model-backed edit for this case yet. The console does not invent one.</p>';
      return;
    }
    const field = edit.field || "question";
    const before = field === "answer" ? displayAnswer(data.answer) : String(data[field] || "");
    const after = before.includes(edit.find ?? "") ? before.replace(edit.find ?? "", edit.replace ?? "") : before;
    $("#diff-state").textContent = "One suggested change";
    const wordsBefore = String(edit.find || "").trim().split(/\s+/).filter(Boolean);
    const wordsAfter = String(edit.replace || "").trim().split(/\s+/).filter(Boolean);
    const wordDiff = document.createElement("div"); wordDiff.className = "word-diff";
    wordDiff.innerHTML = `<span>Change</span><del>${escapeHtml(wordsBefore.join(" ") || "∅")}</del><b aria-hidden="true">→</b><ins>${escapeHtml(wordsAfter.join(" ") || "∅")}</ins>`;
    const panes = document.createElement("div"); panes.className = "diff-panes";
    const makePane = (label, value, mark, key) => {
      const pane = document.createElement("div"); pane.className = "diff-pane"; pane.innerHTML = `<span class="diff-pane-label">${label}</span>`;
      const content = document.createElement("div"); content.className = "diff-rendered";
      if (field === "answer") content.textContent = value;
      else content.append(diffHtml(value, mark, key));
      pane.append(content); return pane;
    };
    panes.append(makePane("BEFORE", before, edit.find, "diff-old"), makePane("AFTER", after, edit.replace, "diff-new"));
    container.append(wordDiff, panes);
  }
  function renderSelected() {
    const item = cases[selected]; if (!item) return;
    const data = getPayload(item); const action = caseAction(item); const result = item.result;
    $("#case-content").hidden = false;
    $("#case-subject").textContent = item.subject;
    $("#case-qid").textContent = item.id;
    $("#case-type").textContent = item.question.questionType === "integerQuestion" ? "INTEGER" : item.question.questionType.toUpperCase();
    $("#case-level").textContent = item.question.level || "Unrated";
    $("#case-title").textContent = item.title;
    $("#case-meta").textContent = `${item.question.chapter || item.subject} · ${item.reports.length} student report${item.reports.length === 1 ? "" : "s"}`;
    const verdict = action.action === "approved" ? "Approved locally" : result ? result.verdict.replaceAll("_", " ") : "Analysis pending";
    $("#verdict-text").textContent = verdict;
    $("#verdict-badge").className = `verdict-badge ${result ? result.verdict : "pending"}`;
    renderHtml($("#question-preview"), data.question || "<p>Question content unavailable.</p>");
    renderHtml($("#solution-preview"), data.solution || "<p>No solution is stored for this question.</p>");
    $("#preview-title").textContent = result?.edit?.field === "question" ? "Original question" : "Stored question";
    $("#repair-heading").textContent = result ? `${verdict.charAt(0).toUpperCase()}${verdict.slice(1)}${result.repair ? ` · ${result.repair.replaceAll("_", " ")}` : ""}` : "Awaiting analysis";
    $("#evidence").textContent = result?.evidence || "This case has deterministic checks and student comments only. LLM triage has not run.";
    const confidence = result?.confidence;
    $("#confidence-text").textContent = confidence == null ? "Not scored" : `${Math.round(confidence * 100)}%`;
    $("#confidence-fill").style.width = confidence == null ? "0%" : `${Math.round(confidence * 100)}%`;
    $("#repair-label").textContent = result ? `Repair · ${result.repair?.replaceAll("_", " ") || "none"}  ·  Route · ${result.route}` : "No repair selected · LLM route pending";
    const guardItems = item.internal?.guard_outcomes || [];
    $("#guard-list").replaceChildren();
    if (guardItems.length) for (const guard of guardItems) {
      const li = document.createElement("li"); li.innerHTML = `<span class="guard-icon ${guard.status}">${guard.status === "passed" ? "✓" : "!"}</span><span><strong>${escapeHtml(guard.guard.replaceAll("_", " "))}</strong><small>${escapeHtml(guard.detail)}</small></span>`; $("#guard-list").append(li);
    }
    else $("#guard-list").innerHTML = '<li class="guard-empty">No model guard results are available for this case yet.</li>';
    $("#comment-list").replaceChildren(); $("#reporter-heading").textContent = `${item.reports.length} report${item.reports.length === 1 ? "" : "s"}`;
    for (const report of item.reports) {
      const block = document.createElement("article"); block.className = "comment-block";
      block.innerHTML = `<div class="comment-meta"><span>${escapeHtml(report.reportId)}</span><span>${escapeHtml(report.source || "student")}</span></div><p></p><small>${escapeHtml(new Date(report.reportedAt).toLocaleString())}</small>`;
      block.querySelector("p").textContent = report.comment || "(empty report)"; $("#comment-list").append(block);
    }
    $("#reply-list").replaceChildren();
    for (const report of item.reports) {
      const reply = item.resultRows.find(row => row.reportId === report.reportId)?.student_reply;
      const block = document.createElement("div"); block.className = "reply-preview";
      block.innerHTML = `<span>${escapeHtml(report.reportId)}</span><p></p>`;
      block.querySelector("p").textContent = reply || "A student-facing reply will appear after analysis. No reply has been generated."; $("#reply-list").append(block);
    }
    renderDiff(item); renderAudit(item);
    $("#undo").hidden = action.action !== "approved";
    $("#action-copy").textContent = action.action === "approved" ? "Approved in this browser only. Source records are unchanged." : "Your decision is recorded in this browser’s append-only audit log.";
    $("#approve").disabled = action.action === "approved";
    $("#edit").disabled = action.action === "approved";
    $("#reject").disabled = action.action === "approved";
    renderQueue();
  }
  function recordDecision(action, reason = "") {
    const item = cases[selected]; if (!item) return;
    state.actions[item.id] = { ...(state.actions[item.id] || {}), action, reason, route: action === "approved" ? "resolved" : "faculty_review" };
    addAudit(item, action, reason); saveState(); renderSelected(); toast(action === "approved" ? "Approval recorded locally." : "Rejection recorded locally.");
  }
  function startEdit() {
    const item = cases[selected]; const edit = item && currentEdit(item);
    $("#edit-form").hidden = false;
    $("#edit-field").value = edit?.field || "question";
    $("#edit-find").value = edit?.find || "";
    $("#edit-replace").value = edit?.replace || "";
    $("#edit-find").focus();
  }
  function saveEdit() {
    const item = cases[selected]; if (!item) return;
    const field = $("#edit-field").value; const find = $("#edit-find").value; const replace = $("#edit-replace").value;
    if (!find) return toast("Enter the exact text to find.");
    const data = getPayload(item); const target = field === "answer" ? displayAnswer(data.answer) : String(data[field] || "");
    if (target.split(find).length - 1 !== 1) return toast("The text must appear exactly once in the selected field.");
    state.actions[item.id] = { ...(state.actions[item.id] || {}), edit: { field, find, replace }, action: "approved", route: "resolved" };
    addAudit(item, "edited_and_approved", `${field}: ${find} → ${replace}`); saveState(); $("#edit-form").hidden = true; renderSelected(); toast("Edit saved to this browser’s review state.");
  }
  function move(delta) {
    const list = visibleCases(); if (!list.length) return;
    const currentId = cases[selected]?.id; let position = list.findIndex(item => item.id === currentId);
    position = (position + delta + list.length) % list.length;
    selected = cases.findIndex(item => item.id === list[position].id); renderSelected();
  }
  function renderUnreported(items) {
    $("#unreported-count").textContent = items ? String(items.length) : "—";
    if (!items) return;
    $("#unreported-copy").textContent = items.length ? "Candidates from the all-question scan. These still need faculty confirmation." : "The all-question scan found no unreported deterministic candidates.";
    $("#unreported-list").replaceChildren();
    for (const item of items) {
      const row = document.createElement("div"); row.className = "unreported-row";
      row.innerHTML = `<strong>${escapeHtml(item.questionId || item._id || "Question")}</strong><span>${escapeHtml(item.finding || item.code || "candidate")}</span><p>${escapeHtml(item.detail || "Review candidate")}</p>`; $("#unreported-list").append(row);
    }
  }
  function bind() {
    $("#search").addEventListener("input", e => { searchText = e.target.value.trim().toLowerCase(); renderQueue(); });
    document.querySelectorAll(".filter").forEach(button => button.addEventListener("click", () => {
      document.querySelectorAll(".filter").forEach(item => item.classList.toggle("active", item === button));
      activeFilter = button.dataset.filter; renderQueue();
    }));
    $("#previous").addEventListener("click", () => move(-1)); $("#next").addEventListener("click", () => move(1));
    $("#approve").addEventListener("click", () => recordDecision("approved"));
    $("#reject").addEventListener("click", () => {
      const reason = $("#reject-reason")?.value.trim() || "";
      if (!reason) return toast("Add a short reason before rejecting this case.");
      recordDecision("rejected", reason); $("#reject-reason").value = "";
    });
    $("#edit").addEventListener("click", startEdit); $("#save-edit").addEventListener("click", saveEdit);
    $("#close-edit").addEventListener("click", () => { $("#edit-form").hidden = true; });
    $("#undo").addEventListener("click", () => {
      const item = cases[selected]; if (!item) return;
      state.actions[item.id] = { ...(state.actions[item.id] || {}), action: null, route: "faculty_review" };
      addAudit(item, "undo_approval", "Approval reversed in local demo history."); saveState(); renderSelected(); toast("Approval undone in local review state.");
    });
    $("#export-audit").addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(state.audit, null, 2)], { type: "application/json" });
      const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "acadza-audit.json"; link.click(); URL.revokeObjectURL(link.href);
    });
    document.addEventListener("keydown", event => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.target.matches("input, textarea, select, [contenteditable=true]")) return;
      if (event.key.toLowerCase() === "j") move(1);
      if (event.key.toLowerCase() === "k") move(-1);
      if (event.key.toLowerCase() === "a") $("#approve").click();
      if (event.key.toLowerCase() === "r") $("#reject-reason")?.focus();
      if (event.key.toLowerCase() === "e") startEdit();
    });
  }
  async function boot() {
    bind();
    const [questions, reports, results, internal, unreported] = await Promise.all([
      fetchJson("../data/questions.json", []), fetchJson("../data/reports.json", []),
      fetchJson("../results.json", []), fetchJson("../data/internal_cases.json", []),
      fetchJson("../data/unreported_defects.json", null),
    ]);
    cases = makeCases(questions, reports, results, internal);
    if (cases.length) {
      const firstInQueue = [...cases].sort((a, b) => urgency(b) - urgency(a) || b.reports.length - a.reports.length || a.id.localeCompare(b.id))[0];
      selected = cases.findIndex(item => item.id === firstInQueue.id);
    }
    const analyzed = cases.some(item => item.result);
    $("#load-state").innerHTML = analyzed
      ? `<strong>${results.length} precomputed report decisions loaded.</strong> This console does not call an LLM. Approvals and audit entries are stored locally in this browser.`
      : `<strong>LLM analysis is pending.</strong> This console is offline and makes no model calls. It shows the supplied questions and comments; no verdicts or repairs have been invented.`;
    renderUnreported(unreported); renderQueue(); renderSelected();
  }
  boot().catch(error => { const status = $("#load-state"); status.textContent = `Could not load assignment data: ${error.message}`; console.error(error); });
})();
