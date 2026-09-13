import {
  analyzeContributions,
  contributionLevels,
  normalizeUsername,
  normalizeYear,
  parseContributionHtml
} from "../../_lib/contributions.js";

export async function onRequestGet(context) {
  try {
    const username = normalizeUsername(context.params.username);
    const year = normalizeYear(new URL(context.request.url).searchParams.get("year"));
    const from = `${year}-01-01`;
    const to = `${year}-12-31`;
    const githubUrl = `https://github.com/users/${username}/contributions?from=${from}&to=${to}`;

    const response = await fetch(githubUrl, {
      headers: {
        "User-Agent": "github-graph-stego-web/0.1",
        Accept: "text/html"
      },
      cf: {
        cacheTtl: 300,
        cacheEverything: true
      }
    });

    if (!response.ok) {
      return json(
        {
          error: `GitHub returned ${response.status}. Try again later or check the username.`
        },
        response.status
      );
    }

    const html = await response.text();
    const contributions = parseContributionHtml(html);

    if (contributions.length === 0) {
      return json(
        {
          error: "No contribution calendar data was found. GitHub may have changed the page markup."
        },
        502
      );
    }

    return json(
      {
        username,
        year,
        fetched_at: new Date().toISOString(),
        analysis: analyzeContributions(contributions),
        contributions: contributionLevels(contributions)
      },
      200,
      {
        "Cache-Control": "public, max-age=300"
      }
    );
  } catch (error) {
    return json({ error: error.message || "Profile analysis failed." }, 400);
  }
}

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...headers
    }
  });
}
