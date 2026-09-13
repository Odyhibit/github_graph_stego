const form = document.querySelector("#profile-form");
const usernameInput = document.querySelector("#username");
const yearInput = document.querySelector("#year");
const statusBox = document.querySelector("#status");
const results = document.querySelector("#results");

const currentYear = new Date().getFullYear();
yearInput.value = String(currentYear);
yearInput.max = String(currentYear + 1);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  const year = yearInput.value.trim();

  if (!username) {
    showStatus("Enter a GitHub username.", "error");
    return;
  }

  showStatus(`Analyzing ${username}'s ${year} contribution graph...`, "loading");
  results.hidden = true;

  try {
    const response = await fetch(`/api/profile/${encodeURIComponent(username)}?year=${encodeURIComponent(year)}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Analysis failed.");
    }

    renderResults(payload);
    statusBox.hidden = true;
  } catch (error) {
    showStatus(error.message || "Analysis failed.", "error");
  }
});

function renderResults(payload) {
  const { analysis, contributions, username, year } = payload;
  const score = analysis.suspicion_score;

  document.querySelector("#score-title").textContent = `${score.toFixed(1)} / 100`;
  document.querySelector("#score-summary").textContent =
    `${analysis.interpretation.level} signal. ${analysis.interpretation.summary}`;
  document.querySelector("#score-meter span").style.width = `${score}%`;
  document.querySelector("#score-meter").dataset.level = analysis.interpretation.level.toLowerCase();

  document.querySelector("#metric-days").textContent = formatNumber(analysis.total_days);
  document.querySelector("#metric-active").textContent = formatNumber(analysis.days_with_commits);
  document.querySelector("#metric-commits").textContent = formatNumber(analysis.total_commits);
  document.querySelector("#metric-average").textContent = analysis.avg_commits_per_active_day.toFixed(1);
  document.querySelector("#calendar-caption").textContent = `${username} in ${year}`;

  renderCalendar(contributions);
  renderSignals(analysis.signals);
  renderBreakdown(analysis);

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCalendar(contributions) {
  const calendar = document.querySelector("#calendar");
  calendar.textContent = "";

  appendLeadingCalendarBlanks(calendar, contributions);

  for (const day of contributions) {
    const cell = document.createElement("span");
    cell.className = `day ${day.bucket}`;
    cell.title = `${day.date}: ${day.count} contributions`;
    cell.setAttribute("aria-label", `${day.date}: ${day.count} contributions`);
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

function renderSignals(signals) {
  const target = document.querySelector("#signals");
  target.textContent = "";

  for (const signal of signals) {
    const item = document.createElement("article");
    item.className = signal.active ? "signal active" : "signal";
    item.innerHTML = `
      <div>
        <h3>${escapeHtml(signal.label)}</h3>
        <p>${escapeHtml(signal.detail)}</p>
      </div>
      <strong>${escapeHtml(signal.value)}</strong>
    `;
    target.appendChild(item);
  }
}

function renderBreakdown(analysis) {
  const target = document.querySelector("#breakdown");
  const stego = analysis.stego_pattern_analysis;
  const rows = [
    ["1 commit", stego.breakdown["1"] || 0],
    ["5 commits", stego.breakdown["5"] || 0],
    ["10 commits", stego.breakdown["10"] || 0],
    ["16+ commits", stego.marker_days],
    ["Other active counts", Object.values(stego.other_counts).reduce((sum, value) => sum + value, 0)]
  ];
  const max = Math.max(1, ...rows.map(([, value]) => value));

  target.textContent = "";
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "breakdown-row";
    row.innerHTML = `
      <span>${escapeHtml(label)}</span>
      <div class="bar" aria-hidden="true"><i style="width: ${(value / max) * 100}%"></i></div>
      <strong>${formatNumber(value)}</strong>
    `;
    target.appendChild(row);
  }
}

function showStatus(message, type) {
  statusBox.textContent = message;
  statusBox.className = `status ${type}`;
  statusBox.hidden = false;
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
