#!/usr/bin/env python3
"""
GitHub Contribution Scraper (No Token Required)

Scrapes contribution data from public GitHub profiles without API authentication.
Useful for detecting stat padding and analyzing contribution patterns.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class GitHubContributionScraper:
    """Scrapes contribution data from public GitHub profiles."""

    def __init__(self, username: str):
        """
        Initialize scraper.

        Args:
            username: GitHub username to scrape
        """
        self.username = username
        self.base_url = f"https://github.com/{username}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_contribution_data(self, year: Optional[int] = None) -> List[Dict[str, any]]:
        """
        Scrape contribution data from GitHub profile.

        Uses GitHub's internal calendar endpoint which doesn't require authentication.

        Args:
            year: Specific year to fetch (None for current year)

        Returns:
            List of dicts with 'date' and 'count' keys

        Raises:
            requests.RequestException: If request fails
        """
        # Use GitHub's internal calendar endpoint
        # This endpoint returns HTML fragments with contribution data
        if year is None:
            from datetime import datetime as dt
            year = dt.now().year

        # GitHub's calendar endpoint
        calendar_url = f"https://github.com/users/{self.username}/contributions?from={year}-01-01&to={year}-12-31"

        logger.info(f"Fetching contribution data for {self.username} (year: {year})")

        try:
            response = requests.get(calendar_url, headers=self.headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch contribution data: {e}")
            raise

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all contribution day elements
        contributions = []

        # Method 1: Look for <tool-tip> or <td> elements with data attributes
        # GitHub uses different structures, let's try multiple approaches

        # Try finding tool-tip elements (newer GitHub UI)
        tooltips = soup.find_all('tool-tip')
        if tooltips:
            for tooltip in tooltips:
                # Parse the tooltip text like "5 contributions on January 1, 2024"
                text = tooltip.get_text(strip=True)
                date_elem = tooltip.find_previous('td')
                if date_elem:
                    date_str = date_elem.get('data-date')
                    level = date_elem.get('data-level')

                    # Extract count from text
                    if 'No contributions' in text:
                        count = 0
                    else:
                        # Extract number from "X contributions"
                        import re
                        match = re.search(r'(\d+)\s+contribution', text)
                        count = int(match.group(1)) if match else 0

                    if date_str:
                        contributions.append({
                            'date': date_str,
                            'count': count,
                            'level': int(level) if level else None
                        })

        # Method 2: Look for td elements with data-date (older/simpler GitHub UI)
        if not contributions:
            cells = soup.find_all('td', {'data-date': True})
            for cell in cells:
                date_str = cell.get('data-date')
                level = cell.get('data-level')

                # Try to get count from adjacent elements or aria-label
                count = 0
                aria_label = cell.get('aria-label', '')
                if 'No contributions' in aria_label:
                    count = 0
                else:
                    import re
                    match = re.search(r'(\d+)\s+contribution', aria_label)
                    count = int(match.group(1)) if match else 0

                contributions.append({
                    'date': date_str,
                    'count': count,
                    'level': int(level) if level else None
                })

        # Method 3: Look for rect elements (SVG-based)
        if not contributions:
            rects = soup.find_all('rect', {'data-date': True})
            for rect in rects:
                date_str = rect.get('data-date')
                count_str = rect.get('data-count', '0')
                level = rect.get('data-level', '0')

                contributions.append({
                    'date': date_str,
                    'count': int(count_str) if count_str else 0,
                    'level': int(level) if level else None
                })

        if contributions:
            logger.info(f"Scraped {len(contributions)} days of contribution data")
        else:
            logger.warning(f"Could not find contribution data. User may not exist or endpoint changed.")

        return contributions

    def analyze_patterns(self, contributions: List[Dict[str, any]]) -> Dict[str, any]:
        """
        Analyze contribution patterns for suspicious activity.

        Args:
            contributions: List of contribution dicts

        Returns:
            Analysis results dict
        """
        if not contributions:
            return {"error": "No data to analyze"}

        total_days = len(contributions)
        days_with_commits = [c for c in contributions if c['count'] > 0]
        total_commits = sum(c['count'] for c in contributions)

        # Look for exact patterns matching steganography. Empty days can carry
        # 00, so this active-day scraper tracks visible payload and marker days.
        stego_pattern_counts = {1: 0, 5: 0, 10: 0}
        marker_count = 0
        other_counts = {}

        for c in days_with_commits:
            count = c['count']
            if count in stego_pattern_counts:
                stego_pattern_counts[count] += 1
            elif count >= 16:
                marker_count += 1
            else:
                other_counts[count] = other_counts.get(count, 0) + 1

        # Calculate suspicion score
        total_active_days = len(days_with_commits)
        stego_days = sum(stego_pattern_counts.values())
        stego_percentage = (stego_days / total_active_days * 100) if total_active_days > 0 else 0

        # Check for regular patterns (e.g., every weekday has activity)
        weekday_pattern = self._check_weekday_pattern(contributions)

        analysis = {
            'total_days': total_days,
            'days_with_commits': len(days_with_commits),
            'total_commits': total_commits,
            'avg_commits_per_active_day': total_commits / len(days_with_commits) if days_with_commits else 0,
            'stego_pattern_analysis': {
                'days_with_stego_counts': stego_days,
                'marker_days': marker_count,
                'stego_percentage': stego_percentage,
                'breakdown': stego_pattern_counts,
                'other_counts': other_counts
            },
            'weekday_pattern_detected': weekday_pattern,
            'suspicion_score': self._calculate_suspicion_score(
                stego_percentage, weekday_pattern, stego_pattern_counts, other_counts
            )
        }

        return analysis

    def _check_weekday_pattern(self, contributions: List[Dict[str, any]]) -> bool:
        """
        Check if commits only occur on weekdays (suspicious for steganography).

        Args:
            contributions: List of contribution dicts

        Returns:
            True if primarily weekday pattern detected
        """
        weekday_commits = 0
        weekend_commits = 0

        for c in contributions:
            if c['count'] > 0:
                date_obj = datetime.strptime(c['date'], '%Y-%m-%d')
                if date_obj.weekday() < 5:  # Monday-Friday
                    weekday_commits += 1
                else:
                    weekend_commits += 1

        if weekday_commits == 0:
            return False

        weekday_ratio = weekday_commits / (weekday_commits + weekend_commits)
        return weekday_ratio > 0.95  # 95%+ weekday activity is suspicious

    def _calculate_suspicion_score(
        self,
        stego_percentage: float,
        weekday_pattern: bool,
        stego_counts: Dict[int, int],
        other_counts: Dict[int, int]
    ) -> float:
        """
        Calculate a suspicion score (0-100) for stat padding/steganography.

        Args:
            stego_percentage: Percentage of days with stego-like counts
            weekday_pattern: Whether weekday-only pattern detected
            stego_counts: Count of days with 1, 5, 10 commits
            other_counts: Count of days with other commit numbers

        Returns:
            Suspicion score (0-100, higher = more suspicious)
        """
        score = 0.0

        # Factor 1: High percentage of exact stego payload counts (1, 5, 10)
        if stego_percentage > 80:
            score += 40
        elif stego_percentage > 60:
            score += 30
        elif stego_percentage > 40:
            score += 20
        elif stego_percentage > 20:
            score += 10

        # Factor 2: Weekday-only pattern
        if weekday_pattern:
            score += 25

        # Factor 3: Diversity of commit counts
        # Natural activity has varied commit counts
        total_stego = sum(stego_counts.values())
        total_other = sum(other_counts.values())

        if total_stego > 0 and total_other == 0:
            # ONLY visible stego payload counts - very suspicious
            score += 25
        elif total_other > 0:
            diversity = len(other_counts)
            if diversity < 3:
                score += 10  # Low diversity is suspicious

        # Factor 4: Balance of visible stego payload counts
        # If all three visible payload counts are used roughly equally, it's suspicious
        if total_stego > 0:
            stego_values = [v for v in stego_counts.values() if v > 0]
            if len(stego_values) == 3:  # All three visible payload counts used
                # Check if they're roughly balanced (within 2x of each other)
                min_val = min(stego_values)
                max_val = max(stego_values)
                if max_val / min_val < 3:  # Suspiciously balanced
                    score += 10

        return min(100.0, score)

    def detect_backdating(self, username: str, repo_name: str) -> Dict[str, any]:
        """
        Detect if commits in a repository are backdated.

        This requires checking actual commit metadata, not just the contribution graph.

        Args:
            username: GitHub username
            repo_name: Repository name

        Returns:
            Analysis of commit timestamps
        """
        # Note: This would require the GitHub API or git clone + analysis
        # For now, return a placeholder showing the approach
        logger.warning("Backdate detection requires repository access (not yet implemented)")

        return {
            "method": "Would require cloning repo and checking GIT_AUTHOR_DATE vs GIT_COMMITTER_DATE",
            "indicators": [
                "All commits at exact same time (e.g., 12:00:00)",
                "Author date != committer date",
                "Sequential commits with same timestamp",
                "Commits dated before repository creation"
            ]
        }


def main():
    """Demo usage of the scraper."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape GitHub contributions without API token"
    )
    parser.add_argument("username", help="GitHub username to analyze")
    parser.add_argument("--year", type=int, help="Specific year to analyze")
    parser.add_argument("--analyze", action="store_true", help="Analyze for suspicious patterns")

    args = parser.parse_args()

    scraper = GitHubContributionScraper(args.username)

    try:
        contributions = scraper.get_contribution_data(args.year)

        if not contributions:
            print(f"No contribution data found for {args.username}")
            return

        print(f"\n=== Contribution Data for {args.username} ===")
        print(f"Total days: {len(contributions)}")
        print(f"Days with activity: {sum(1 for c in contributions if c['count'] > 0)}")
        print(f"Total commits: {sum(c['count'] for c in contributions)}")

        if args.analyze:
            print("\n=== Suspicious Pattern Analysis ===")
            analysis = scraper.analyze_patterns(contributions)

            print(f"\nSuspicion Score: {analysis['suspicion_score']:.1f}/100")

            if analysis['suspicion_score'] > 70:
                print("⚠️  HIGH SUSPICION - Likely stat padding or steganography")
            elif analysis['suspicion_score'] > 40:
                print("⚠️  MODERATE SUSPICION - Unusual patterns detected")
            else:
                print("✓ LOW SUSPICION - Patterns appear natural")

            print(f"\nSteganography Pattern Match:")
            stego = analysis['stego_pattern_analysis']
            print(f"  Days with stego payload counts (1/5/10): {stego['days_with_stego_counts']}")
            print(f"  Darkest-green marker days (16+): {stego['marker_days']}")
            print(f"  Percentage: {stego['stego_percentage']:.1f}%")
            print(f"  Breakdown: {stego['breakdown']}")

            if analysis['weekday_pattern_detected']:
                print(f"\n⚠️  Weekday-only pattern detected (suspicious)")

            print(f"\nOther commit counts: {stego['other_counts']}")

            # Show sample of suspicious days
            suspicious_days = [c for c in contributions if c['count'] in [1, 5, 10] or c['count'] >= 16]
            if suspicious_days:
                print(f"\nSample of days with steganographic payload/marker counts (first 10):")
                for day in suspicious_days[:10]:
                    print(f"  {day['date']}: {day['count']} commits")

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
