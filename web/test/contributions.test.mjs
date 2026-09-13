import assert from "node:assert/strict";
import test from "node:test";
import {
  analyzeContributions,
  contributionLevels,
  normalizeUsername,
  normalizeYear,
  parseContributionHtml
} from "../functions/_lib/contributions.js";

test("parses contribution cells with aria labels and data-count attributes", () => {
  const html = `
    <td data-date="2026-01-01" data-level="0" aria-label="No contributions on January 1, 2026"></td>
    <td data-date="2026-01-02" data-level="1" aria-label="1 contribution on January 2, 2026"></td>
    <rect data-date="2026-01-03" data-count="5" data-level="2"></rect>
  `;

  assert.deepEqual(parseContributionHtml(html), [
    { date: "2026-01-01", count: 0, level: 0 },
    { date: "2026-01-02", count: 1, level: 1 },
    { date: "2026-01-03", count: 5, level: 2 }
  ]);
});

test("scores a highly patterned contribution calendar", () => {
  const contributions = [
    { date: "2026-01-05", count: 20 },
    { date: "2026-01-06", count: 1 },
    { date: "2026-01-07", count: 5 },
    { date: "2026-01-08", count: 10 },
    { date: "2026-01-09", count: 1 },
    { date: "2026-01-12", count: 5 },
    { date: "2026-01-13", count: 10 },
    { date: "2026-01-14", count: 20 }
  ];

  const analysis = analyzeContributions(contributions);

  assert.equal(analysis.weekday_pattern_detected, true);
  assert.equal(analysis.stego_pattern_analysis.marker_days, 2);
  assert.equal(analysis.interpretation.level, "High");
  assert.equal(analysis.suspicion_score, 80);
});

test("does not treat common low stego-count overlap as a positive signal", () => {
  const contributions = [
    { date: "2026-01-01", count: 1 },
    { date: "2026-01-02", count: 2 },
    { date: "2026-01-03", count: 3 },
    { date: "2026-01-04", count: 4 },
    { date: "2026-01-05", count: 6 },
    { date: "2026-01-06", count: 8 }
  ];

  const analysis = analyzeContributions(contributions);
  const stegoSignal = analysis.signals.find((signal) => signal.label === "Stego-like visible counts");

  assert.equal(analysis.stego_pattern_analysis.stego_percentage.toFixed(1), "16.7");
  assert.equal(stegoSignal.active, false);
  assert.equal(analysis.suspicion_score, 0);
});

test("detects repetitive same-count cadence", () => {
  const contributions = [
    { date: "2026-01-01", count: 12 },
    { date: "2026-01-02", count: 12 },
    { date: "2026-01-03", count: 12 },
    { date: "2026-01-04", count: 12 },
    { date: "2026-01-05", count: 12 },
    { date: "2026-01-06", count: 12 },
    { date: "2026-01-07", count: 12 },
    { date: "2026-01-08", count: 12 },
    { date: "2026-01-09", count: 12 },
    { date: "2026-01-10", count: 12 }
  ];

  const analysis = analyzeContributions(contributions);
  const cadenceSignal = analysis.signals.find((signal) => signal.label === "Repetitive cadence");

  assert.equal(analysis.repetition_analysis.repeated_count_detected, true);
  assert.equal(analysis.repetition_analysis.longest_same_count_streak, 10);
  assert.equal(cadenceSignal.active, true);
  assert.equal(analysis.suspicion_score, 15);
});

test("labels contribution buckets for the heatmap", () => {
  assert.deepEqual(
    contributionLevels([
      { date: "2026-01-01", count: 0 },
      { date: "2026-01-02", count: 1 },
      { date: "2026-01-03", count: 5 },
      { date: "2026-01-04", count: 10 },
      { date: "2026-01-05", count: 16 }
    ]).map((day) => day.bucket),
    ["empty", "low", "medium", "high", "marker"]
  );
});

test("validates public input", () => {
  assert.equal(normalizeUsername("octocat"), "octocat");
  assert.throws(() => normalizeUsername("-bad"));
  assert.equal(normalizeYear("2026", new Date("2026-09-13T00:00:00Z")), 2026);
  assert.throws(() => normalizeYear("2000", new Date("2026-09-13T00:00:00Z")));
});
