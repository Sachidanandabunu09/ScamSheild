"use strict";

const $ = id => document.getElementById(id);
const labels = {low_risk: "Low indicators", suspicious: "Needs review", high_risk: "High risk"};
const summaries = {
  low_risk: "No strong warning signs found. Still verify unexpected requests.",
  suspicious: "Some signs deserve a closer look. Verify before taking action.",
  high_risk: "Strong warning signs found. Avoid acting on this request without verification."
};
const examples = {
  message: [
    ["KYC request", "Dear customer, your SBI account will be blocked today. Update KYC immediately: http://sbi-kyc-update221.xyz/login"],
    ["Bank alert", "Rs 1,200 debited from A/c XX4521. Avl bal Rs 15,300. -HDFCBK"],
    ["Normal chat", "Hey, are we meeting at the cafe at 6 today?"]
  ],
  url: [
    ["Fake bank", "http://hdfc-secure-verify.top/login"],
    ["Short link", "https://rb.gy/example"],
    ["Recognized domain", "https://www.sbi.co.in"]
  ]
};
let mode = "message";
let busy = false;
let recent = [];
const drafts = {message: "", url: ""};
const resultPanel = document.querySelector(".result-panel");

function resetResult() {
  $("result").hidden = true;
  $("error").hidden = true;
  $("status").hidden = false;
  $("status-title").textContent = "A little clarity goes a long way.";
  $("status-copy").textContent = "Add a message or link, and we’ll help you spot the signs worth a second look.";
  $("result-state").textContent = "Awaiting input";
}

function updateInput() {
  $("character-count").textContent = $("input").value.length.toLocaleString() + " / 2,000";
  $("clear-input").disabled = busy || !$("input").value.length;
  drafts[mode] = $("input").value;
}

function setMode(next) {
  drafts[mode] = $("input").value;
  mode = next;
  $("input-label").textContent = next === "message" ? "Paste your message" : "Paste a website link";
  $("input").placeholder = next === "message"
    ? "Paste an SMS, WhatsApp message, or email excerpt here…" : "https://example.com";
  $("input-help").textContent = next === "message"
    ? "English text · 3–2,000 characters" : "HTTP or HTTPS · 3–2,000 characters";
  $("input").value = drafts[next];
  $("submit-label").textContent = next === "message" ? "Analyze message" : "Analyze link";
  $("examples").replaceChildren();
  examples[next].forEach(([name, text]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = name;
    button.onclick = () => {
      $("input").value = text;
      updateInput();
      resetResult();
      $("input").focus({preventScroll: true});
    };
    $("examples").append(button);
  });
  updateInput();
  resetResult();
}

function setBusy(value) {
  busy = value;
  resultPanel.setAttribute("aria-busy", String(value));
  $("check-form").querySelectorAll("button, input, textarea").forEach(element => {
    element.disabled = value;
  });
  $("submit-label").textContent = value ? "Analyzing…"
    : mode === "message" ? "Analyze message" : "Analyze link";
  updateInput();
}

function renderHistory() {
  $("history").replaceChildren();
  $("history-empty").hidden = recent.length > 0;
  $("history-table").hidden = recent.length === 0;
  $("clear").disabled = recent.length === 0;
  $("nav-count").textContent = String(recent.length);
  $("history-count").textContent = String(recent.length);
  recent.forEach(item => {
    const row = document.createElement("tr");
    const type = document.createElement("td");
    type.className = "type-cell";
    type.textContent = item.kind === "url" ? "Link" : "Message";
    const input = document.createElement("td");
    input.textContent = item.input;
    const assessment = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "verdict-badge " + item.verdict;
    badge.textContent = labels[item.verdict];
    assessment.append(badge);
    const score = document.createElement("td");
    score.className = "score-cell";
    score.textContent = item.score + " / 100";
    row.append(type, input, assessment, score);
    $("history").append(row);
  });
}

function serviceStatus(online) {
  $("service-status").classList.toggle("offline", !online);
  $("service-label").textContent = online ? "System online" : "Service unavailable";
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health", {signal: AbortSignal.timeout(5000)});
    const data = await response.json();
    serviceStatus(response.ok && data.status === "ok");
  } catch {
    serviceStatus(false);
  }
}

async function loadStats() {
  try {
    const response = await fetch("/api/stats", {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error();
    const data = await response.json();
    $("stats").textContent = data.total_checks.toLocaleString() + " checks across all visitors · Last "
      + data.retention_days + " days · Only counts are stored";
  } catch {
    $("stats").textContent = "Usage counts are temporarily unavailable.";
  }
}

function showResult(data) {
  if (!Object.hasOwn(labels, data.verdict) || !Number.isFinite(data.score)
      || data.score < 0 || data.score > 100 || !Array.isArray(data.reasons)) {
    throw new Error("The service returned an unexpected result. Please try again.");
  }
  $("result").className = data.verdict;
  $("verdict").textContent = labels[data.verdict];
  $("result-summary").textContent = summaries[data.verdict];
  $("score").value = data.score;
  $("score-number").textContent = String(data.score);
  $("score-arc").setAttribute("stroke-dashoffset", String(270.18 * (1 - data.score / 100)));
  $("reasons").replaceChildren();
  data.reasons.forEach(reason => {
    const li = document.createElement("li");
    li.textContent = reason;
    $("reasons").append(li);
  });
  $("status").hidden = true;
  $("result").hidden = false;
  $("result-state").textContent = "Analysis complete";
  $("result-title").focus({preventScroll: true});
  if (window.matchMedia("(max-width: 680px)").matches) {
    resultPanel.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
      block: "start"
    });
  }
}

$("check-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  const input = $("input").value.trim();
  resetResult();
  if (input.length < 3 || input.length > 2000) {
    $("error").textContent = "Enter between 3 and 2,000 characters.";
    $("error").hidden = false;
    $("status").hidden = true;
    $("result-state").textContent = "Check your input";
    $("input").focus();
    return;
  }
  const submittedMode = mode;
  setBusy(true);
  $("status-title").textContent = "Taking a closer look…";
  $("status-copy").textContent = "Checking patterns and link indicators. Your input won’t be saved.";
  $("result-state").textContent = "Analyzing";
  try {
    const response = await fetch("/api/check/" + submittedMode, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(submittedMode === "message" ? {text: input} : {url: input}),
      signal: AbortSignal.timeout(15000)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status >= 500) serviceStatus(false);
      throw new Error(response.status === 429 ? "Too many checks. Wait one minute and try again."
        : typeof data.detail === "string" ? data.detail : "The service is unavailable. Please try again.");
    }
    showResult(data);
    serviceStatus(true);
    recent.unshift({
      kind: submittedMode,
      input: input.length > 120 ? input.slice(0, 120) + "…" : input,
      verdict: data.verdict, score: data.score
    });
    recent = recent.slice(0, 8);
    renderHistory();
    void loadStats();
  } catch (error) {
    $("status").hidden = true;
    $("result").hidden = true;
    $("error").hidden = false;
    $("result-state").textContent = "Couldn’t complete";
    $("error").textContent = error.name === "TimeoutError" ? "The check timed out. Please try again."
      : error instanceof TypeError ? "Cannot connect to the service. Check your connection and try again."
      : error.message;
    if (error instanceof TypeError || error.name === "TimeoutError") void checkHealth();
  } finally {
    setBusy(false);
  }
});

$("input").addEventListener("input", () => { updateInput(); resetResult(); });
$("input").addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    $("check-form").requestSubmit();
  }
});
$("clear-input").onclick = () => {
  $("input").value = "";
  updateInput();
  resetResult();
  $("input").focus();
};
document.querySelectorAll('input[name="mode"]').forEach(element => {
  element.addEventListener("change", () => setMode(element.value));
});
$("clear").onclick = () => { recent = []; renderHistory(); };
document.querySelectorAll(".nav-item").forEach(link => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(item => {
      item.classList.remove("active");
      item.removeAttribute("aria-current");
    });
    link.classList.add("active");
    link.setAttribute("aria-current", "location");
  });
});
$("environment").textContent = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname)
  ? "Local preview" : "Hosted instance";
setMode(mode);
renderHistory();
void checkHealth();
void loadStats();
