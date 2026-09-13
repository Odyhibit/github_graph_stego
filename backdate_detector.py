#!/usr/bin/env python3
"""
Backdated Commit Detector

Analyzes git repositories for backdated commits (common in stat padding).
"""

import subprocess
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import Counter
import statistics

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class BackdateDetector:
    """Detects backdated commits in git repositories."""

    def __init__(self, repo_url: str, local_path: Optional[str] = None):
        """
        Initialize detector.

        Args:
            repo_url: GitHub repository URL
            local_path: Path to local clone (will clone if None)
        """
        self.repo_url = repo_url
        self.local_path = local_path

    def clone_or_pull(self, target_dir: str = "/tmp/backdate_check") -> str:
        """
        Clone repository or pull if already exists.

        Args:
            target_dir: Directory to clone into

        Returns:
            Path to repository
        """
        if self.local_path:
            logger.info(f"Using existing repository at {self.local_path}")
            return self.local_path

        import os
        import shutil

        repo_name = self.repo_url.split("/")[-1].replace(".git", "")
        full_path = os.path.join(target_dir, repo_name)

        if os.path.exists(full_path):
            logger.info(f"Repository already exists at {full_path}, pulling updates...")
            try:
                subprocess.run(
                    ['git', 'pull'],
                    cwd=full_path,
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError:
                logger.warning("Pull failed, will use existing state")
        else:
            logger.info(f"Cloning {self.repo_url} to {full_path}...")
            os.makedirs(target_dir, exist_ok=True)
            subprocess.run(
                ['git', 'clone', self.repo_url, full_path],
                check=True,
                capture_output=True
            )

        self.local_path = full_path
        return full_path

    def get_commit_metadata(self) -> List[Dict[str, any]]:
        """
        Extract all commit metadata including timestamps.

        Returns:
            List of commit metadata dicts
        """
        if not self.local_path:
            raise ValueError("Repository not cloned. Call clone_or_pull() first.")

        # Git log format: commit hash, author date, committer date, author name, subject
        git_format = "--pretty=format:%H|%aI|%cI|%an|%ae|%s"

        result = subprocess.run(
            ['git', 'log', git_format, '--all'],
            cwd=self.local_path,
            capture_output=True,
            text=True,
            check=True
        )

        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split('|')
            if len(parts) >= 6:
                commit_hash, author_date, committer_date, author_name, author_email, subject = parts[:6]

                commits.append({
                    'hash': commit_hash,
                    'author_date': author_date,
                    'committer_date': committer_date,
                    'author_name': author_name,
                    'author_email': author_email,
                    'subject': subject,
                    'date_diff': self._parse_date_diff(author_date, committer_date)
                })

        logger.info(f"Extracted {len(commits)} commits")
        return commits

    def _parse_date_diff(self, author_date: str, committer_date: str) -> float:
        """
        Calculate difference between author and committer dates in seconds.

        Args:
            author_date: ISO format date string
            committer_date: ISO format date string

        Returns:
            Difference in seconds
        """
        try:
            ad = datetime.fromisoformat(author_date.replace('Z', '+00:00'))
            cd = datetime.fromisoformat(committer_date.replace('Z', '+00:00'))
            return (cd - ad).total_seconds()
        except:
            return 0.0

    def analyze_backdating(self, commits: List[Dict[str, any]]) -> Dict[str, any]:
        """
        Analyze commits for backdating indicators.

        Args:
            commits: List of commit metadata

        Returns:
            Analysis results
        """
        if not commits:
            return {"error": "No commits to analyze"}

        # Indicator 1: Large date differences
        date_diffs = [abs(c['date_diff']) for c in commits]
        large_diff_threshold = 60  # 1 minute
        large_diffs = sum(1 for d in date_diffs if d > large_diff_threshold)

        # Indicator 2: Exact timestamp patterns
        author_times = [c['author_date'].split('T')[1][:8] for c in commits]  # HH:MM:SS
        time_counter = Counter(author_times)
        most_common_time, most_common_count = time_counter.most_common(1)[0]

        exact_time_percentage = (most_common_count / len(commits) * 100) if commits else 0

        # Indicator 3: Commits on exact hours (12:00:00, 13:00:00, etc.)
        exact_hours = sum(1 for t in author_times if t.endswith(':00:00'))
        exact_hour_percentage = (exact_hours / len(commits) * 100) if commits else 0

        # Indicator 4: Sequential commits with identical timestamps
        identical_timestamp_sequences = 0
        for i in range(len(commits) - 1):
            if commits[i]['author_date'] == commits[i + 1]['author_date']:
                identical_timestamp_sequences += 1

        # Indicator 5: Commits dated before repository creation
        # (Would need to check first commit in main branch)
        sorted_commits = sorted(commits, key=lambda c: c['author_date'])
        first_commit_date = sorted_commits[0]['author_date'] if sorted_commits else None

        # Indicator 6: Batch backdating (many commits on same day)
        dates = [c['author_date'].split('T')[0] for c in commits]
        date_counter = Counter(dates)
        dates_with_many_commits = sum(1 for count in date_counter.values() if count > 10)

        # Calculate suspicion score
        suspicion_score = 0.0

        if large_diffs > len(commits) * 0.1:  # >10% have large diff
            suspicion_score += 20

        if exact_time_percentage > 50:  # >50% at same time
            suspicion_score += 30

        if exact_hour_percentage > 30:  # >30% at exact hours
            suspicion_score += 25

        if identical_timestamp_sequences > len(commits) * 0.2:  # >20% identical
            suspicion_score += 15

        if dates_with_many_commits > 5:  # Many days with 10+ commits
            suspicion_score += 10

        analysis = {
            'total_commits': len(commits),
            'date_difference_analysis': {
                'commits_with_large_diff': large_diffs,
                'percentage': (large_diffs / len(commits) * 100) if commits else 0,
                'avg_diff_seconds': sum(date_diffs) / len(date_diffs) if date_diffs else 0,
                'max_diff_seconds': max(date_diffs) if date_diffs else 0
            },
            'timestamp_patterns': {
                'most_common_time': most_common_time,
                'most_common_time_count': most_common_count,
                'exact_time_percentage': exact_time_percentage,
                'exact_hour_percentage': exact_hour_percentage
            },
            'sequential_patterns': {
                'identical_timestamp_sequences': identical_timestamp_sequences,
                'percentage': (identical_timestamp_sequences / len(commits) * 100) if commits else 0
            },
            'date_distribution': {
                'dates_with_many_commits': dates_with_many_commits,
                'max_commits_per_day': max(date_counter.values()) if date_counter else 0,
                'avg_commits_per_day': sum(date_counter.values()) / len(date_counter) if date_counter else 0
            },
            'first_commit': first_commit_date,
            'suspicion_score': min(100.0, suspicion_score)
        }

        return analysis

    def find_suspicious_commits(
        self,
        commits: List[Dict[str, any]],
        threshold: float = 60.0
    ) -> List[Dict[str, any]]:
        """
        Find commits that are likely backdated.

        Args:
            commits: List of commit metadata
            threshold: Date diff threshold in seconds

        Returns:
            List of suspicious commits
        """
        suspicious = []

        for commit in commits:
            is_suspicious = False
            reasons = []

            # Check 1: Large date difference
            if abs(commit['date_diff']) > threshold:
                is_suspicious = True
                reasons.append(f"Large date diff: {commit['date_diff']:.0f}s")

            # Check 2: Exact hour timestamp
            time = commit['author_date'].split('T')[1][:8]
            if time.endswith(':00:00'):
                is_suspicious = True
                reasons.append(f"Exact hour: {time}")

            # Check 3: Suspicious commit message patterns
            if any(pattern in commit['subject'].lower() for pattern in ['update', 'data.txt']):
                reasons.append(f"Generic message: {commit['subject']}")

            if is_suspicious or reasons:
                suspicious.append({
                    **commit,
                    'suspicion_reasons': reasons
                })

        return suspicious


def main():
    """Demo usage of the backdate detector."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect backdated commits in git repositories"
    )
    parser.add_argument("repo_url", help="GitHub repository URL")
    parser.add_argument("--local", help="Path to local repository clone")
    parser.add_argument("--show-suspicious", action="store_true", help="Show suspicious commits")

    args = parser.parse_args()

    detector = BackdateDetector(args.repo_url, args.local)

    try:
        # Clone or use local repo
        if not args.local:
            detector.clone_or_pull()

        # Get commit metadata
        commits = detector.get_commit_metadata()

        if not commits:
            print("No commits found in repository")
            return 1

        # Analyze for backdating
        print(f"\n=== Backdating Analysis ===")
        analysis = detector.analyze_backdating(commits)

        print(f"\nTotal commits: {analysis['total_commits']}")
        print(f"\nSuspicion Score: {analysis['suspicion_score']:.1f}/100")

        if analysis['suspicion_score'] > 70:
            print("⚠️  HIGH SUSPICION - Repository likely contains backdated commits")
        elif analysis['suspicion_score'] > 40:
            print("⚠️  MODERATE SUSPICION - Some unusual patterns detected")
        else:
            print("✓ LOW SUSPICION - Commit timestamps appear natural")

        # Date difference analysis
        diff_analysis = analysis['date_difference_analysis']
        print(f"\nDate Difference Analysis:")
        print(f"  Commits with author ≠ committer date: {diff_analysis['commits_with_large_diff']}")
        print(f"  Percentage: {diff_analysis['percentage']:.1f}%")
        print(f"  Average difference: {diff_analysis['avg_diff_seconds']:.1f}s")

        # Timestamp patterns
        ts_analysis = analysis['timestamp_patterns']
        print(f"\nTimestamp Patterns:")
        print(f"  Most common time: {ts_analysis['most_common_time']} ({ts_analysis['most_common_time_count']} commits)")
        print(f"  Exact time percentage: {ts_analysis['exact_time_percentage']:.1f}%")
        print(f"  Exact hour percentage: {ts_analysis['exact_hour_percentage']:.1f}%")

        if ts_analysis['exact_time_percentage'] > 50:
            print("  ⚠️  WARNING: >50% of commits at same exact time (highly suspicious)")

        # Show suspicious commits
        if args.show_suspicious:
            print(f"\n=== Suspicious Commits ===")
            suspicious = detector.find_suspicious_commits(commits)

            if suspicious:
                print(f"Found {len(suspicious)} suspicious commits (showing first 10):\n")
                for commit in suspicious[:10]:
                    print(f"Commit: {commit['hash'][:8]}")
                    print(f"  Date: {commit['author_date']}")
                    print(f"  Subject: {commit['subject']}")
                    print(f"  Reasons: {', '.join(commit['suspicion_reasons'])}")
                    print()
            else:
                print("No highly suspicious commits found")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
