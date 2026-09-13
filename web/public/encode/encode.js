const BITS_PER_CHARACTER = 8;
const BITS_PER_CHUNK = 2;
const PAYLOAD_DAYS_PER_CHARACTER = BITS_PER_CHARACTER / BITS_PER_CHUNK;
const MARKER_COMMITS = 20;
const HINT_COMMITS = 10;
const ARROW_GAP_WEEKS = 3;
const COMMIT_LEVELS = {
  "00": 0,
  "01": 1,
  "10": 5,
  "11": 10
};

const scanForm = document.querySelector("#scan-form");
const encodeForm = document.querySelector("#encode-form");
const usernameInput = document.querySelector("#username");
const yearInput = document.querySelector("#year");
const messageInput = document.querySelector("#message");
const modeInput = document.querySelector("#mode");
const startDateInput = document.querySelector("#start-date");
const arrowHintInput = document.querySelector("#arrow-hint");
const statusBox = document.querySelector("#status");
const scanResults = document.querySelector("#scan-results");
const previewSection = document.querySelector("#preview-section");
const planSection = document.querySelector("#plan-section");
const fitSummary = document.querySelector("#fit-summary");
const cliCommand = document.querySelector("#cli-command code");
const copyCommandButton = document.querySelector("#copy-command");
const commandUserInput = document.querySelector("#command-user");
const commandRepoInput = document.querySelector("#command-repo");
const createRepoInput = document.querySelector("#create-repo");

let currentPayload = null;
let currentScan = null;

const currentYear = new Date().getFullYear();
yearInput.value = String(currentYear);
yearInput.max = String(currentYear + 1);

scanForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  const year = yearInput.value.trim();

  if (!username) {
    showStatus("Enter a GitHub username.", "error");
    return;
  }

  showStatus(`Scanning ${username}'s ${year} contribution graph...`, "loading");
  scanResults.hidden = true;
  previewSection.hidden = true;
  planSection.hidden = true;

  try {
    const response = await fetch(`/api/profile/${encodeURIComponent(username)}?year=${encodeURIComponent(year)}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Scan failed.");
    }

    currentPayload = payload;
    currentScan = scanEmptyRanges(payload.contributions);
    renderScan(payload, currentScan);
    statusBox.hidden = true;
  } catch (error) {
    showStatus(error.message || "Scan failed.", "error");
  }
});

encodeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!currentPayload || !currentScan) {
    showStatus("Scan a profile before previewing an encoding plan.", "error");
    return;
  }

  try {
    const message = messageInput.value;
    const weekdaysOnly = modeInput.value === "weekdays";
    const startDate = startDateInput.value;
    const plan = buildCommitPlan(message, startDate, weekdaysOnly, arrowHintInput.checked);
    const preview = mergePlan(currentPayload.contributions, plan);

    renderPreview(preview, plan, message, weekdaysOnly);
    renderPlan(plan, preview.conflicts);
    statusBox.hidden = true;
  } catch (error) {
    showStatus(error.message || "Could not build preview.", "error");
  }
});

modeInput.addEventListener("change", () => {
  if (!currentScan) {
    return;
  }
  setDefaultStartDate();
  updateFitSummary();
});

messageInput.addEventListener("input", updateFitSummary);
startDateInput.addEventListener("input", updateFitSummary);
arrowHintInput.addEventListener("change", () => {
  updateFitSummary();
  updateCliCommand();
});
copyCommandButton.addEventListener("click", copyCliCommand);
commandUserInput.addEventListener("input", updateCliCommand);
commandRepoInput.addEventListener("input", updateCliCommand);
createRepoInput.addEventListener("change", updateCliCommand);

function renderScan(payload, scan) {
  document.querySelector("#metric-empty").textContent = `${scan.longestAllDays.length} days`;
  document.querySelector("#metric-weekday-empty").textContent = `${scan.longestWeekdays.length} days`;
  document.querySelector("#metric-weekday-capacity").textContent =
    `${capacityFromEncodingDays(scan.longestWeekdays.length)} chars`;
  document.querySelector("#metric-all-capacity").textContent =
    `${capacityFromEncodingDays(scan.longestAllDays.length)} chars`;
  document.querySelector("#current-caption").textContent = `${payload.username} in ${payload.year}`;
  if (!commandUserInput.value.trim()) {
    commandUserInput.value = payload.username;
  }
  if (!commandRepoInput.value.trim()) {
    commandRepoInput.value = `graph-stego-${payload.year}`;
  }

  renderCalendar("#current-calendar", payload.contributions);
  renderCandidates(scan);
  setDefaultStartDate();
  updateFitSummary();

  scanResults.hidden = false;
  scanResults.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCandidates(scan) {
  const target = document.querySelector("#candidate-list");
  const candidates = [
    ["Best weekday range", scan.longestWeekdays, "Skips weekends while encoding."],
    ["Best all-day range", scan.longestAllDays, "Uses every calendar day."]
  ];

  target.textContent = "";
  for (const [label, range, detail] of candidates) {
    const item = document.createElement("article");
    item.className = "candidate";
    item.innerHTML = `
      <div>
        <h3>${escapeHtml(label)}</h3>
        <p>${escapeHtml(detail)}</p>
      </div>
      <strong>${range.length ? `${range.start} to ${range.end}` : "None"}</strong>
      <button type="button" ${range.length ? "" : "disabled"}>Use</button>
    `;
    item.querySelector("button").addEventListener("click", () => {
      startDateInput.value = range.start;
      modeInput.value = label.includes("weekday") ? "weekdays" : "all-days";
      updateFitSummary();
    });
    target.appendChild(item);
  }
}

function renderCalendar(selector, contributions, plannedByDate = new Map()) {
  const calendar = document.querySelector(selector);
  calendar.textContent = "";

  appendLeadingCalendarBlanks(calendar, contributions);

  for (const day of contributions) {
    const planned = plannedByDate.get(day.date);
    const cell = document.createElement("span");
    const classes = ["day", day.bucket || bucketForCount(day.count)];
    const titleParts = [`${day.date}: ${day.count} current contributions`];

    if (planned) {
      classes.push(planned.cssClass);
      titleParts.push(`${planned.label}: ${planned.commits} planned commits`);
      if (planned.conflict) {
        classes.push("conflict");
        titleParts.push("conflict with existing activity");
      }
    }

    cell.className = classes.join(" ");
    cell.title = titleParts.join(" | ");
    cell.setAttribute("aria-label", titleParts.join(", "));
    calendar.appendChild(cell);
  }
}

function appendLeadingCalendarBlanks(calendar, contributions) {
  const firstDate = contributions[0]?.date;
  if (!firstDate) {
    return;
  }

  const offset = new Date(`${firstDate}T00:00:00Z`).getUTCDay();
  for (let index = 0; index < offset; index += 1) {
    const blank = document.createElement("span");
    blank.className = "day calendar-blank";
    blank.setAttribute("aria-hidden", "true");
    calendar.appendChild(blank);
  }
}

function renderPreview(preview, plan, message, weekdaysOnly) {
  renderCalendar("#preview-calendar", preview.contributions, preview.plannedByDate);

  const payloadDays = plan.filter((step) => step.kind !== "hint").length;
  const hintDays = plan.length - payloadDays;
  const conflicts = preview.conflicts.length;
  const finalDate = maxPlanDate(plan);
  document.querySelector("#preview-caption").textContent =
    `${message.length} chars, ${payloadDays} payload days${
      hintDays ? `, ${hintDays} hint days` : ""
    }, ends ${finalDate}`;

  fitSummary.hidden = false;
  fitSummary.className = conflicts ? "fit-summary warning" : "fit-summary good";
  fitSummary.innerHTML = `
    <strong>${conflicts ? "Conflicts found" : "Clean preview"}</strong>
    <span>${escapeHtml(message.length.toString())} characters require ${payloadDays} ${
      weekdaysOnly ? "weekday" : "calendar"
    } payload days${hintDays ? ` plus ${hintDays} arrow-hint days` : ""}. ${
      conflicts ? `${conflicts} planned dates already have activity.` : "Selected dates are empty."
    }</span>
  `;

  previewSection.hidden = false;
}

function renderPlan(plan, conflicts) {
  updateCliCommand();
  planSection.hidden = false;
}

function buildCliCommand(message, startDate, weekdaysOnly) {
  const githubUser = commandUserInput.value.trim() || "username";
  const repoName = sanitizeRepoName(commandRepoInput.value.trim()) || "graph-stego-message";
  const localRepoPath = `./${repoName}`;
  const remoteUrl = `git@github.com:${githubUser}/${repoName}.git`;
  const parts = [
    "graph-stego-encode",
    shellQuote(message),
    "--start",
    shellQuote(startDate),
    "--repo",
    shellQuote(localRepoPath),
    "--remote",
    shellQuote(remoteUrl),
    "--push"
  ];

  if (!weekdaysOnly) {
    parts.push("--all-days");
  }

  if (arrowHintInput.checked) {
    parts.push("--arrow-hint");
  }

  const encodeCommand = parts.join(" ");

  if (!createRepoInput.checked) {
    return encodeCommand;
  }

  return [
    `gh repo create ${shellQuote(`${githubUser}/${repoName}`)} --public`,
    `mkdir -p ${shellQuote(localRepoPath)}`,
    encodeCommand
  ].join("\n");
}

function updateCliCommand() {
  if (!cliCommand || !messageInput.value || !startDateInput.value) {
    return;
  }

  cliCommand.textContent = buildCliCommand(
    messageInput.value,
    startDateInput.value,
    modeInput.value === "weekdays"
  );
  copyCommandButton.textContent = "Copy CLI Command";
}

async function copyCliCommand() {
  const command = cliCommand.textContent.trim();
  if (!command) {
    return;
  }

  try {
    await navigator.clipboard.writeText(command);
    copyCommandButton.textContent = "Copied";
  } catch {
    copyCommandButton.textContent = "Select and copy";
  }
}

function scanEmptyRanges(contributions) {
  const longestAllDays = longestEmptyRange(contributions, () => true);
  const longestWeekdays = longestEmptyRange(contributions, (day) => isWeekday(day.date));
  return { longestAllDays, longestWeekdays };
}

function longestEmptyRange(contributions, isEligible) {
  let best = emptyRange();
  let current = emptyRange();

  for (const day of contributions) {
    if (!isEligible(day)) {
      continue;
    }

    if (day.count === 0) {
      if (!current.length) {
        current = { start: day.date, end: day.date, length: 1 };
      } else {
        current.end = day.date;
        current.length += 1;
      }

      if (current.length > best.length) {
        best = { ...current };
      }
    } else {
      current = emptyRange();
    }
  }

  return best;
}

function emptyRange() {
  return { start: "", end: "", length: 0 };
}

function setDefaultStartDate() {
  const range = modeInput.value === "weekdays" ? currentScan.longestWeekdays : currentScan.longestAllDays;
  if (range?.start) {
    startDateInput.value = range.start;
  }
}

function updateFitSummary() {
  if (!currentScan || !messageInput.value || !startDateInput.value) {
    fitSummary.hidden = true;
    return;
  }

  try {
    const plan = buildCommitPlan(
      messageInput.value,
      startDateInput.value,
      modeInput.value === "weekdays",
      arrowHintInput.checked
    );
    const preview = mergePlan(currentPayload.contributions, plan);
    const clean = preview.conflicts.length === 0;
    const payloadDays = plan.filter((step) => step.kind !== "hint").length;
    const hintDays = plan.length - payloadDays;
    fitSummary.hidden = false;
    fitSummary.className = clean ? "fit-summary good" : "fit-summary warning";
    fitSummary.innerHTML = `
      <strong>${clean ? "Looks possible" : "Needs another window"}</strong>
      <span>${messageInput.value.length} chars need ${payloadDays} payload days${
        hintDays ? ` and ${hintDays} hint days` : ""
      }, ending on ${maxPlanDate(plan)}. ${
        clean ? "No existing contributions overlap." : `${preview.conflicts.length} selected dates already have activity.`
      }</span>
    `;
  } catch {
    fitSummary.hidden = true;
  }
}

function buildCommitPlan(message, startDate, weekdaysOnly, includeArrowHint = false) {
  if (!message || message.length > 24) {
    throw new Error("Enter a short message up to 24 characters.");
  }
  if (!/^[\x20-\x7E]+$/.test(message)) {
    throw new Error("Use printable ASCII characters for this first planner.");
  }
  if (!startDate) {
    throw new Error("Choose a start date.");
  }

  const chunks = messageToChunks(message);
  let cursor = nextEligibleDate(startDate, weekdaysOnly);
  const plan = [{ date: cursor, commits: MARKER_COMMITS, label: "start marker", bits: "", kind: "marker" }];
  cursor = addDays(cursor, 1);

  for (const bits of chunks) {
    cursor = nextEligibleDate(cursor, weekdaysOnly);
    plan.push({
      date: cursor,
      commits: COMMIT_LEVELS[bits],
      label: COMMIT_LEVELS[bits] === 0 ? "empty payload" : "payload",
      bits,
      kind: "payload"
    });
    cursor = addDays(cursor, 1);
  }

  cursor = nextEligibleDate(cursor, weekdaysOnly);
  plan.push({ date: cursor, commits: MARKER_COMMITS, label: "end marker", bits: "", kind: "marker" });

  if (!includeArrowHint) {
    return plan;
  }

  const arrowPlan = buildArrowHintPlan(plan[0].date, cursor, currentPayload?.year);
  return [...plan, ...arrowPlan].sort((first, second) => first.date.localeCompare(second.date));
}

function buildArrowHintPlan(startDate, endDate, year) {
  const leftPlan = arrowDates("left", startDate, endDate);
  if (arrowFitsYear(leftPlan, year)) {
    return leftPlan;
  }

  const rightPlan = arrowDates("right", startDate, endDate);
  if (arrowFitsYear(rightPlan, year)) {
    return rightPlan;
  }

  throw new Error("There is not enough room in this year for a separated arrow hint.");
}

function arrowDates(side, startDate, endDate) {
  const offsets =
    side === "left"
      ? [
          [-1, 1],
          [-1, 2],
          [0, 2],
          [-4, 3],
          [-3, 3],
          [-2, 3],
          [-1, 3],
          [0, 3],
          [1, 3],
          [-1, 4],
          [0, 4],
          [-1, 5]
        ]
      : [
          [1, 1],
          [0, 2],
          [1, 2],
          [-1, 3],
          [0, 3],
          [1, 3],
          [2, 3],
          [3, 3],
          [4, 3],
          [0, 4],
          [1, 4],
          [1, 5]
        ];
  const anchorWeek =
    side === "left"
      ? addDays(weekStart(startDate), -ARROW_GAP_WEEKS * 7)
      : addDays(weekStart(endDate), ARROW_GAP_WEEKS * 7);

  return offsets
    .map(([weekOffset, dayOffset]) => ({
      date: addDays(anchorWeek, weekOffset * 7 + dayOffset),
      commits: HINT_COMMITS,
      label: side === "left" ? "arrow hint ->" : "<- arrow hint",
      bits: "",
      kind: "hint"
    }))
    .sort((first, second) => first.date.localeCompare(second.date));
}

function arrowFitsYear(plan, year) {
  if (!year) {
    return true;
  }
  return plan.every((step) => step.date.startsWith(`${year}-`));
}

function messageToChunks(message) {
  const binary = [...message]
    .map((char) => char.charCodeAt(0).toString(2).padStart(8, "0"))
    .join("");
  const chunks = [];
  for (let index = 0; index < binary.length; index += BITS_PER_CHUNK) {
    chunks.push(binary.slice(index, index + BITS_PER_CHUNK).padEnd(BITS_PER_CHUNK, "0"));
  }
  return chunks;
}

function mergePlan(contributions, plan) {
  const plannedByDate = new Map();
  const currentByDate = new Map(contributions.map((day) => [day.date, day]));
  const conflicts = [];

  for (const step of plan) {
    const current = currentByDate.get(step.date);
    if (!current) {
      conflicts.push({ date: step.date, current: null, planned: step.commits, reason: "outside scanned year" });
      plannedByDate.set(step.date, {
        ...step,
        conflict: true,
        cssClass: plannedClassForCommits(step.commits)
      });
      continue;
    }

    const conflict = Boolean(current && current.count > 0);
    if (conflict) {
      conflicts.push({ date: step.date, current: current.count, planned: step.commits, reason: "existing activity" });
    }
    plannedByDate.set(step.date, {
      ...step,
      conflict,
      cssClass: plannedClassForCommits(step.commits)
    });
  }

  return { contributions, plannedByDate, conflicts };
}

function nextEligibleDate(date, weekdaysOnly) {
  let cursor = date;
  while (weekdaysOnly && !isWeekday(cursor)) {
    cursor = addDays(cursor, 1);
  }
  return cursor;
}

function addDays(date, amount) {
  const parsed = new Date(`${date}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + amount);
  return parsed.toISOString().slice(0, 10);
}

function weekStart(date) {
  const parsed = new Date(`${date}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() - parsed.getUTCDay());
  return parsed.toISOString().slice(0, 10);
}

function maxPlanDate(plan) {
  return plan.reduce((latest, step) => (step.date > latest ? step.date : latest), plan[0]?.date || "n/a");
}

function isWeekday(date) {
  const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
  return weekday >= 1 && weekday <= 5;
}

function capacityFromEncodingDays(days) {
  return Math.max(0, Math.floor((days - 2) / PAYLOAD_DAYS_PER_CHARACTER));
}

function bucketForCount(count) {
  if (count === 0) {
    return "empty";
  }
  if (count < 3) {
    return "low";
  }
  if (count < 8) {
    return "medium";
  }
  if (count < 16) {
    return "high";
  }
  return "marker";
}

function plannedClassForCommits(commits) {
  if (commits === 0) {
    return "planned-zero";
  }
  if (commits < 3) {
    return "planned-payload-low";
  }
  if (commits < 8) {
    return "planned-payload-medium";
  }
  if (commits < 16) {
    return "planned-payload-high";
  }
  return "planned-marker";
}

function showStatus(message, type) {
  statusBox.textContent = message;
  statusBox.className = `status ${type}`;
  statusBox.hidden = false;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function sanitizeRepoName(value) {
  return value.replace(/[^a-zA-Z0-9._-]/g, "-").replace(/^-+|-+$/g, "");
}
