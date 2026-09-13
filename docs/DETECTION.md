# Stat Padding & Steganography Detection

This document explains how to use the detection tools to identify users who may be padding their GitHub stats or using steganography.

## Overview

Two complementary tools are provided:

1. **graph-stego-scrape** - Scrapes contribution data from public profiles (no API token required)
2. **graph-stego-detect-backdating** - Analyzes git repositories for backdated commits

## Tool 1: Contribution Pattern Scraper

### How It Works

The scraper extracts contribution data from GitHub's public contribution graph without requiring authentication. It then analyzes patterns that are characteristic of:
- Stat padding (artificially inflating commit counts)
- Steganographic encoding (hiding data in contribution patterns)
- Automated commit generation

### Key Detection Indicators

#### 1. Steganographic Commit Counts
The steganography tool uses empty days for `00`, exactly **1, 5, or 10 commits** per day for visible payload data, and **20+ commits** as darkest-green start/end markers. If a user has a high percentage of days with these exact visible payload counts plus rare marker days, it's suspicious.

**Suspicion Thresholds:**
- \>80% stego payload counts: HIGH suspicion (40 points)
- \>60% stego payload counts: MODERATE-HIGH (30 points)
- \>40% stego payload counts: MODERATE (20 points)
- \>20% stego payload counts: LOW-MODERATE (10 points)

#### 2. Weekday-Only Pattern
Steganographic encoding often uses weekdays only for more natural-looking patterns. If 95%+ of commits are on weekdays, this adds 25 suspicion points.

#### 3. Lack of Diversity
Natural coding activity produces varied commit counts. If only the steganographic payload counts (1, 5, 10) and marker-like 20+ count days appear with no other values, this adds 25 points.

#### 4. Balanced Distribution
If all three visible payload counts appear with roughly equal frequency (suspicious statistical balance), this adds 10 points.

### Usage Examples

```bash
# Basic usage - scrape contribution data
graph-stego-scrape username

# Analyze a specific year
graph-stego-scrape username --year 2024

# Analyze for suspicious patterns
graph-stego-scrape username --year 2024 --analyze
```

### Sample Output

```
=== Contribution Data for username ===
Total days: 365
Days with activity: 180
Total commits: 950

=== Suspicious Pattern Analysis ===

Suspicion Score: 85.0/100
HIGH SUSPICION - Likely stat padding or steganography

Steganography Pattern Match:
  Days with stego payload counts (1/5/10): 173
  Darkest-green marker days (16+): 2
  Percentage: 97.2%
  Breakdown: {1: 58, 5: 57, 10: 58}

Weekday-only pattern detected (suspicious)

Other commit counts: {2: 3, 3: 2}
```

### Suspicion Score Interpretation

| Score | Interpretation | Action |
|-------|----------------|--------|
| 0-30 | Low suspicion | Natural activity pattern |
| 30-50 | Moderate suspicion | Review manually, could be coincidence |
| 50-70 | High suspicion | Likely using automation or stat padding |
| 70-100 | Very high suspicion | Almost certainly steganography or stat padding |

## Tool 2: Backdated Commit Detector

### How It Works

This tool clones a GitHub repository and analyzes actual commit metadata to detect backdating. Backdated commits are a key component of stat padding, as they allow users to manipulate their contribution history.

### Key Detection Indicators

#### 1. Author Date ≠ Committer Date
Git stores two timestamps:
- **Author Date**: When the commit was originally created
- **Committer Date**: When the commit was added to the repository

Legitimate rebases/cherry-picks cause small differences (seconds/minutes). Large differences (hours/days) indicate backdating.

**Detection:** Commits with >60 second difference are flagged.

#### 2. Exact Time Patterns
Natural commits occur at varied times. If many commits have identical timestamps or occur at exact hours (12:00:00, 13:00:00), it's suspicious.

**Detection:**
- \>50% of commits at same exact time: 30 points
- \>30% of commits at exact hours: 25 points

#### 3. Sequential Identical Timestamps
Multiple sequential commits with identical timestamps are impossible in normal workflow (Git would use different timestamps).

**Detection:** \>20% identical sequential timestamps: 15 points

#### 4. Batch Commit Days
Many commits (10+) on a single day, repeated across multiple days, suggests automated backdating.

**Detection:** \>5 days with 10+ commits: 10 points

### Usage Examples

```bash
# Analyze a GitHub repository
graph-stego-detect-backdating https://github.com/username/repo

# Use a local repository clone
graph-stego-detect-backdating https://github.com/username/repo --local /path/to/repo

# Show suspicious commits
graph-stego-detect-backdating https://github.com/username/repo --show-suspicious
```

### Sample Output

```
=== Backdating Analysis ===

Total commits: 234

Suspicion Score: 95.0/100
HIGH SUSPICION - Repository likely contains backdated commits

Date Difference Analysis:
  Commits with author ≠ committer date: 230
  Percentage: 98.3%
  Average difference: 3600.0s

Timestamp Patterns:
  Most common time: 12:00:00 (230 commits)
  Exact time percentage: 98.3%
  Exact hour percentage: 98.3%
  WARNING: >50% of commits at same exact time (highly suspicious)

=== Suspicious Commits ===
Found 230 suspicious commits (showing first 10):

Commit: a1b2c3d4
  Date: 2024-01-01T12:00:00
  Subject: Update data.txt
  Reasons: Large date diff: 3600s, Exact hour: 12:00:00, Generic message: Update data.txt
```

## Combined Detection Strategy

For the most accurate detection, use both tools together:

### Step 1: Scrape Contribution Pattern
```bash
graph-stego-scrape suspicious_user --year 2024 --analyze
```

**Look for:**
- High suspicion score (>70)
- High percentage of stego payload counts (1, 5, 10) plus rare 20+ marker days
- Weekday-only pattern

### Step 2: Analyze Repository Commits
```bash
graph-stego-detect-backdating https://github.com/suspicious_user/repo --show-suspicious
```

**Look for:**
- High suspicion score (>70)
- Many commits at exact same time
- Large author/committer date differences
- Generic commit messages ("Update", "data.txt")

### Step 3: Manual Verification

If both tools report high suspicion:

1. **Check the repository content**
   - Does it contain real code or just dummy files?
   - Is `data.txt` the only modified file?
   - Are commit messages meaningful?

2. **Examine commit history**
   ```bash
   git log --pretty=format:"%ai | %ci | %s" | head -20
   ```
   - Look for patterns in timestamps
   - Check if all commits touch the same file

3. **Check repository creation date**
   - Commits dated before repo creation are impossible
   - Visible on GitHub repo page

## Common Stat Padding Patterns

### Pattern 1: Pure Steganography
- 95-100% of visible payload commits are 1, 5, or 10, with 20+ marker days
- Weekday-only activity
- All commits at 12:00:00
- Single repository with dummy content
- **Detection:** Both tools will show 90-100 suspicion score

### Pattern 2: Hybrid Padding
- Mix of real commits and padded commits
- Steganographic counts appear regularly but not exclusively
- Multiple repositories with varying content
- **Detection:** Moderate suspicion (40-70) on both tools

### Pattern 3: Naive Padding
- High commit counts but irregular patterns
- Not using steganographic specific counts
- Still shows backdating indicators
- **Detection:** High on backdate detector, lower on scraper

## False Positives

Some legitimate scenarios can trigger suspicion:

1. **Automated CI/CD commits**
   - May occur at regular intervals
   - Check commit messages for "CI:", "Auto:", etc.

2. **Mass repository imports**
   - Migrating from other VCS systems
   - Check for migration-related commit messages

3. **Bot accounts**
   - Dependabot, Renovate, etc.
   - Check username and commit patterns

4. **Enterprise monorepo activity**
   - Large teams may have frequent commits
   - Check for varied authors and meaningful messages

## Ethical Considerations

### Appropriate Use Cases

**Appropriate:**
- Detecting stat padding for hiring/scholarship decisions
- Identifying steganographic communication in authorized investigations
- Academic research on GitHub activity patterns
- Security audits of developer accounts

**Inappropriate:**
- Harassment or public shaming
- Automated mass-scanning without consent
- Using results as sole criteria for decisions
- Violating privacy laws or GitHub ToS

### Best Practices

1. **Verify manually** - Don't rely solely on automated scores
2. **Consider context** - Understand the user's background and use case
3. **Respect privacy** - Only analyze public data
4. **Be transparent** - If using for decisions, explain detection methods
5. **Allow appeals** - Give users a chance to explain unusual patterns

## Technical Limitations

### Scraper Limitations
- Only sees public contribution data
- Can't distinguish between different repositories
- GitHub may change HTML structure (requires updates)
- Rate limiting may apply for many requests

### Backdate Detector Limitations
- Requires cloning entire repository
- Only analyzes one repository at a time
- Can't detect sophisticated backdating with randomized timestamps
- Storage intensive for large repositories

## Improving Detection

### Reducing False Positives
1. Set higher suspicion thresholds (70+ instead of 50+)
2. Require both tools to agree
3. Check multiple repositories per user
4. Examine commit content and messages

### Catching Sophisticated Padding
1. Analyze commit timing distribution statistically
2. Check for correlation between commit times and repository activity
3. Examine file modification patterns
4. Cross-reference with other activity (issues, PRs, reviews)

## Conclusion

These tools provide effective detection of GitHub stat padding and steganography with minimal setup and no API authentication required. By combining contribution pattern analysis with commit metadata inspection, you can identify suspicious activity with high accuracy.

Remember: **High suspicion scores indicate patterns worth investigating, not proof of wrongdoing.** Always verify findings manually and consider legitimate explanations before taking action.
