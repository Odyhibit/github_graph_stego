const STEGO_COUNTS = [1, 5, 10];
const MARKER_MIN_COMMITS = 16;

export function normalizeYear(value, now = new Date()) {
  const year = value ? Number(value) : now.getUTCFullYear();
  if (!Number.isInteger(year) || year < 2008 || year > now.getUTCFullYear() + 1) {
    throw new Error("Year must be a valid GitHub contribution year.");
  }
  return year;
}

export function normalizeUsername(value) {
  const username = String(value || "").trim();
  if (!/^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$/.test(username)) {
    throw new Error("Enter a valid GitHub username.");
  }
  return username;
}

export function parseContributionHtml(html) {
  const contributions = [];
  const seen = new Set();
  const tagPattern = /<(?:td|rect)\b[^>]*\bdata-date=["'](\d{4}-\d{2}-\d{2})["'][^>]*>/gi;
  let match;

  while ((match = tagPattern.exec(html)) !== null) {
    const tag = match[0];
    const date = match[1];
    if (seen.has(date)) {
      continue;
    }

    const count = extractCount(tag, html, tagPattern.lastIndex);
    const level = extractNumericAttribute(tag, "data-level");
    contributions.push({ date, count, level });
    seen.add(date);
  }

  contributions.sort((a, b) => a.date.localeCompare(b.date));
  return contributions;
}

export function analyzeContributions(contributions) {
  if (!Array.isArray(contributions) || contributions.length === 0) {
    return { error: "No contribution data found." };
  }

  const activeDays = contributions.filter((day) => day.count > 0);
  const totalCommits = contributions.reduce((sum, day) => sum + day.count, 0);
  const breakdown = { 1: 0, 5: 0, 10: 0 };
  const otherCounts = {};
  let markerDays = 0;
  let weekdayCommits = 0;
  let weekendCommits = 0;

  for (const day of activeDays) {
    if (STEGO_COUNTS.includes(day.count)) {
      breakdown[day.count] += 1;
    } else if (day.count >= MARKER_MIN_COMMITS) {
      markerDays += 1;
    } else {
      otherCounts[day.count] = (otherCounts[day.count] || 0) + 1;
    }

    if (isWeekday(day.date)) {
      weekdayCommits += 1;
    } else {
      weekendCommits += 1;
    }
  }

  const stegoDays = Object.values(breakdown).reduce((sum, value) => sum + value, 0);
  const stegoPercentage = activeDays.length ? (stegoDays / activeDays.length) * 100 : 0;
  const weekdayPatternDetected =
    weekdayCommits > 0 && weekdayCommits / (weekdayCommits + weekendCommits) > 0.95;
  const repetition = analyzeRepetition(activeDays);

  const suspicionScore = calculateSuspicionScore(
    stegoPercentage,
    weekdayPatternDetected,
    breakdown,
    otherCounts,
    repetition
  );

  return {
    total_days: contributions.length,
    days_with_commits: activeDays.length,
    total_commits: totalCommits,
    avg_commits_per_active_day: activeDays.length ? totalCommits / activeDays.length : 0,
    weekday_activity: {
      weekday_days: weekdayCommits,
      weekend_days: weekendCommits,
      weekday_ratio: activeDays.length ? weekdayCommits / activeDays.length : 0
    },
    stego_pattern_analysis: {
      days_with_stego_counts: stegoDays,
      marker_days: markerDays,
      stego_percentage: stegoPercentage,
      breakdown,
      other_counts: otherCounts
    },
    repetition_analysis: repetition,
    weekday_pattern_detected: weekdayPatternDetected,
    suspicion_score: suspicionScore,
    interpretation: interpretScore(suspicionScore),
    signals: buildSignals(
      stegoPercentage,
      weekdayPatternDetected,
      breakdown,
      otherCounts,
      markerDays,
      repetition
    )
  };
}

export function contributionLevels(contributions) {
  return contributions.map((day) => ({
    ...day,
    bucket:
      day.count === 0
        ? "empty"
        : day.count < 3
          ? "low"
          : day.count < 8
            ? "medium"
            : day.count < MARKER_MIN_COMMITS
              ? "high"
              : "marker"
  }));
}

function extractCount(tag, html, nextIndex) {
  const dataCount = extractNumericAttribute(tag, "data-count");
  if (dataCount !== null) {
    return dataCount;
  }

  const aria = extractStringAttribute(tag, "aria-label") || nearbyTooltipText(html, nextIndex);
  if (!aria || /no contributions/i.test(aria)) {
    return 0;
  }

  const countMatch = aria.match(/(\d+)\s+contribution/i);
  return countMatch ? Number(countMatch[1]) : 0;
}

function nearbyTooltipText(html, startIndex) {
  const slice = html.slice(startIndex, startIndex + 600);
  const tooltipMatch = slice.match(/<tool-tip\b[^>]*>([\s\S]*?)<\/tool-tip>/i);
  return tooltipMatch ? decodeHtml(stripTags(tooltipMatch[1])).trim() : "";
}

function extractNumericAttribute(tag, name) {
  const value = extractStringAttribute(tag, name);
  if (value === null || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function extractStringAttribute(tag, name) {
  const pattern = new RegExp(`\\b${name}=["']([^"']*)["']`, "i");
  const match = tag.match(pattern);
  return match ? decodeHtml(match[1]) : null;
}

function stripTags(value) {
  return value.replace(/<[^>]*>/g, " ");
}

function decodeHtml(value) {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function isWeekday(date) {
  const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
  return weekday >= 1 && weekday <= 5;
}

function analyzeRepetition(activeDays) {
  if (activeDays.length === 0) {
    return {
      dominant_count: null,
      dominant_count_days: 0,
      dominant_count_percentage: 0,
      longest_same_count_streak: 0,
      repeated_count_detected: false
    };
  }

  const countFrequency = {};
  for (const day of activeDays) {
    countFrequency[day.count] = (countFrequency[day.count] || 0) + 1;
  }

  const [dominantCount, dominantDays] = Object.entries(countFrequency).sort((a, b) => {
    if (b[1] !== a[1]) {
      return b[1] - a[1];
    }
    return Number(a[0]) - Number(b[0]);
  })[0];

  let longestSameCountStreak = 1;
  let currentStreak = 1;
  const sortedDays = [...activeDays].sort((a, b) => a.date.localeCompare(b.date));

  for (let index = 1; index < sortedDays.length; index += 1) {
    const previous = sortedDays[index - 1];
    const current = sortedDays[index];
    const daysApart = daysBetween(previous.date, current.date);

    if (daysApart === 1 && previous.count === current.count) {
      currentStreak += 1;
    } else {
      currentStreak = 1;
    }

    longestSameCountStreak = Math.max(longestSameCountStreak, currentStreak);
  }

  const dominantPercentage = (dominantDays / activeDays.length) * 100;
  const repeatedCountDetected =
    activeDays.length >= 10 && (dominantPercentage >= 70 || longestSameCountStreak >= 7);

  return {
    dominant_count: Number(dominantCount),
    dominant_count_days: dominantDays,
    dominant_count_percentage: dominantPercentage,
    longest_same_count_streak: longestSameCountStreak,
    repeated_count_detected: repeatedCountDetected
  };
}

function calculateSuspicionScore(
  stegoPercentage,
  weekdayPattern,
  stegoCounts,
  otherCounts,
  repetition
) {
  let score = 0;

  if (stegoPercentage >= 90) {
    score += 40;
  } else if (stegoPercentage >= 80) {
    score += 30;
  } else if (stegoPercentage >= 70) {
    score += 20;
  }

  if (weekdayPattern) {
    score += 25;
  }

  const totalStego = Object.values(stegoCounts).reduce((sum, value) => sum + value, 0);
  const totalOther = Object.values(otherCounts).reduce((sum, value) => sum + value, 0);

  if (stegoPercentage >= 70 && totalStego > 0 && totalOther === 0) {
    score += 25;
  } else if (stegoPercentage >= 70 && totalOther > 0 && Object.keys(otherCounts).length < 3) {
    score += 10;
  }

  const usedStegoValues = Object.values(stegoCounts).filter((value) => value > 0);
  if (stegoPercentage >= 70 && usedStegoValues.length === 3) {
    const min = Math.min(...usedStegoValues);
    const max = Math.max(...usedStegoValues);
    if (min > 0 && max / min < 3) {
      score += 10;
    }
  }

  if (repetition?.repeated_count_detected) {
    score += repetition.longest_same_count_streak >= 14 ? 20 : 15;
  }

  return Math.min(100, score);
}

function interpretScore(score) {
  if (score > 70) {
    return {
      level: "High",
      summary: "The visible pattern strongly resembles automated padding or graph steganography."
    };
  }
  if (score > 40) {
    return {
      level: "Moderate",
      summary: "Some visible patterns are unusual enough to merit a closer manual look."
    };
  }
  return {
    level: "Low",
    summary: "The visible contribution pattern does not strongly match this project's known indicators."
  };
}

function buildSignals(
  stegoPercentage,
  weekdayPattern,
  breakdown,
  otherCounts,
  markerDays,
  repetition
) {
  const signals = [];
  const totalStego = Object.values(breakdown).reduce((sum, value) => sum + value, 0);
  const totalOther = Object.values(otherCounts).reduce((sum, value) => sum + value, 0);

  signals.push({
    label: "Stego-like visible counts",
    value: `${stegoPercentage.toFixed(1)}%`,
    active: stegoPercentage >= 70,
    detail: "Share of active days with exactly 1, 5, or 10 commits. Stronger correlation starts around 70%."
  });

  signals.push({
    label: "Darkest-green marker days",
    value: String(markerDays),
    active: markerDays >= 2,
    detail: "Days with 16 or more commits can act as start/end markers."
  });

  signals.push({
    label: "Weekday concentration",
    value: weekdayPattern ? "Detected" : "Not detected",
    active: weekdayPattern,
    detail: "More than 95% of active days fall on weekdays."
  });

  signals.push({
    label: "Repetitive cadence",
    value: repetition?.repeated_count_detected
      ? `${repetition.dominant_count} daily contributions repeated`
      : "Not detected",
    active: Boolean(repetition?.repeated_count_detected),
    detail: repetition
      ? `${repetition.dominant_count_percentage.toFixed(1)}% of active days share the same public contribution count; longest same-count daily streak is ${repetition.longest_same_count_streak}.`
      : "Looks only for repeated public calendar counts, not repeated code diffs."
  });

  signals.push({
    label: "Count diversity",
    value: totalStego > 0 && totalOther === 0 ? "Very low" : "Mixed",
    active: stegoPercentage >= 70 && totalStego > 0 && totalOther === 0,
    detail: "Natural activity usually has more varied commit counts."
  });

  return signals;
}

function daysBetween(firstDate, secondDate) {
  const first = Date.parse(`${firstDate}T00:00:00Z`);
  const second = Date.parse(`${secondDate}T00:00:00Z`);
  return Math.round((second - first) / 86400000);
}
