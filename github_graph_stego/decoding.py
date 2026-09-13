#!/usr/bin/env python3
"""
GitHub Contribution Graph Steganography Decoder

Extracts hidden messages from GitHub contribution patterns.
"""

import requests
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import argparse
import sys

from github_graph_stego.github import GitHubContributionScraper


# Constants
BITS_PER_BYTE = 8
BITS_PER_CHUNK = 2  # 2-bit encoding for 4 payload states

# ASCII character range for printable characters
ASCII_PRINTABLE_MIN = 32
ASCII_PRINTABLE_MAX = 126

# Commit count tolerance ranges for 2-bit payload decoding. The darkest green
# level is reserved as a start/end marker, so empty days carry the 00 payload.
COMMIT_RANGES = [
    (0, 0, "00"),    # Empty/gray (0 commits) -> 00
    (1, 2, "01"),    # Light green (1-2 commits) -> 01
    (3, 7, "10"),    # Medium-light green (3-7 commits) -> 10
    (8, 15, "11")    # Medium-dark green (8-15 commits) -> 11
]
MARKER_MIN_COMMITS = 16  # Darkest green, reserved for start/end markers

# GitHub GraphQL API endpoint
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class DecodingError(Exception):
    """Custom exception for decoding errors."""
    pass


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""
    pass


class GitHubContributionDecoder:
    """Decodes messages from GitHub contribution graphs."""

    def __init__(self, username: str, token: Optional[str] = None):
        """
        Initialize decoder with GitHub username and optional API token.

        Args:
            username: GitHub username to analyze
            token: GitHub personal access token (optional; enables GraphQL API)
        """
        self.username = username
        self.token = token
        self.api_url = GITHUB_GRAPHQL_API
        self.commit_ranges = COMMIT_RANGES

        if self.token:
            logger.debug("Using GitHub API token for authentication")
        else:
            logger.debug("No GitHub token provided; using public contribution scraping")

    def get_contribution_data(
        self,
        start_date: str,
        end_date: str,
        retry_count: int = 3
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch contribution data.

        Uses public contribution scraping by default. If a token was provided,
        uses GitHub's GraphQL API instead.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            retry_count: Number of retries on failure

        Returns:
            List of dicts with 'date' and 'count' keys

        Raises:
            GitHubAPIError: If API request fails after retries
            ValueError: If date format is invalid
        """
        # Validate date format
        try:
            start_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_obj = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}. Use YYYY-MM-DD")

        if end_obj < start_obj:
            raise ValueError("End date must be on or after start date")

        if not self.token:
            return self._get_public_contribution_data(start_obj, end_obj)

        return self._get_graphql_contribution_data(start_date, end_date, retry_count)

    def _get_public_contribution_data(
        self,
        start_obj: datetime,
        end_obj: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch public contribution data without a token and filter to date range.

        Args:
            start_obj: Start date
            end_obj: End date

        Returns:
            List of dicts with 'date' and 'count' keys
        """
        scraper = GitHubContributionScraper(self.username)
        contributions: List[Dict[str, Any]] = []

        for year in range(start_obj.year, end_obj.year + 1):
            try:
                contributions.extend(scraper.get_contribution_data(year))
            except requests.RequestException as e:
                raise GitHubAPIError(f"Public contribution scrape failed: {e}")

        start_date = start_obj.strftime("%Y-%m-%d")
        end_date = end_obj.strftime("%Y-%m-%d")
        filtered = [
            {"date": c["date"], "count": c["count"]}
            for c in contributions
            if start_date <= c["date"] <= end_date
        ]
        filtered.sort(key=lambda c: c["date"])

        if not filtered:
            raise GitHubAPIError("No public contribution data found")

        logger.debug(f"Fetched {len(filtered)} public contribution days")
        return filtered

    def _get_graphql_contribution_data(
        self,
        start_date: str,
        end_date: str,
        retry_count: int = 3
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch contribution data from GitHub GraphQL API.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            retry_count: Number of retries on failure

        Returns:
            List of dicts with 'date' and 'count' keys

        Raises:
            GitHubAPIError: If API request fails after retries
        """
        query = """
        query($username: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $username) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "username": self.username,
            "from": f"{start_date}T00:00:00Z",
            "to": f"{end_date}T23:59:59Z"
        }

        headers = {
            "Content-Type": "application/json",
        }

        headers["Authorization"] = f"Bearer {self.token}"

        last_error = None
        for attempt in range(retry_count):
            try:
                logger.debug(f"Fetching contribution data (attempt {attempt + 1}/{retry_count})...")
                response = requests.post(
                    self.api_url,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    error_msg = data['errors'][0].get('message', 'Unknown error')
                    raise GitHubAPIError(f"GraphQL Error: {error_msg}")

                # Check if user exists
                if data.get("data", {}).get("user") is None:
                    raise GitHubAPIError(f"User '{self.username}' not found")

                # Flatten the nested structure
                contributions = []
                weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                for week in weeks:
                    for day in week["contributionDays"]:
                        contributions.append({
                            "date": day["date"],
                            "count": day["contributionCount"]
                        })

                logger.debug(f"Fetched {len(contributions)} days of contribution data")
                return contributions

            except requests.exceptions.Timeout as e:
                last_error = f"Request timeout: {e}"
                logger.warning(f"Attempt {attempt + 1} timed out")
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {e}"
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON response: {e}"
                logger.warning(f"Attempt {attempt + 1} received invalid JSON")

        # All retries failed
        raise GitHubAPIError(f"Failed to fetch contribution data after {retry_count} attempts: {last_error}")

    def filter_weekdays(self, contributions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter contributions to only include weekdays (Mon-Fri).

        Args:
            contributions: List of contribution dicts

        Returns:
            Filtered list of contributions
        """
        weekday_contributions = []
        for contrib in contributions:
            date_obj = datetime.strptime(contrib["date"], "%Y-%m-%d")
            # Monday = 0, Sunday = 6
            if date_obj.weekday() < 5:  # Mon-Fri
                weekday_contributions.append(contrib)

        logger.debug(f"Filtered to {len(weekday_contributions)} weekdays from {len(contributions)} total days")
        return weekday_contributions

    def map_commits_to_bits(self, contributions: List[Dict[str, Any]]) -> str:
        """
        Map commit counts between darkest-green markers to bit patterns.

        Args:
            contributions: List of contribution dicts

        Returns:
            Binary string

        Raises:
            DecodingError: If markers are missing or commit count mapping fails
        """
        marker_indices = [
            i for i, contrib in enumerate(contributions)
            if contrib["count"] >= MARKER_MIN_COMMITS
        ]

        if len(marker_indices) < 2:
            raise DecodingError("Could not find start and end markers")

        start_index = marker_indices[0]
        end_index = marker_indices[-1]

        if end_index <= start_index + 1:
            raise DecodingError("No payload data found between markers")

        binary = ""

        for contrib in contributions[start_index + 1:end_index]:
            count = contrib["count"]

            # Find matching range
            matched = False
            for min_count, max_count, bit_pattern in self.commit_ranges:
                if min_count <= count <= max_count:
                    binary += bit_pattern
                    matched = True
                    break

            if not matched:
                raise DecodingError(
                    f"Commit count {count} on {contrib['date']} is reserved for markers"
                )

        return binary

    def binary_to_ascii(self, binary_string: str, strict: bool = False) -> str:
        """
        Convert binary string to ASCII text.

        Args:
            binary_string: String of 0s and 1s
            strict: If True, raise error on non-printable characters

        Returns:
            Decoded ASCII string

        Raises:
            DecodingError: If strict mode and non-printable characters found
        """
        if not binary_string:
            raise DecodingError("Empty binary string")

        # Pad to multiple of 8
        padding = (BITS_PER_BYTE - len(binary_string) % BITS_PER_BYTE) % BITS_PER_BYTE
        if padding > 0:
            logger.debug(f"Padding binary string with {padding} zeros")
        binary_string += "0" * padding

        decoded = ""
        for i in range(0, len(binary_string), BITS_PER_BYTE):
            byte = binary_string[i:i + BITS_PER_BYTE]
            char_code = int(byte, 2)

            # Check if printable ASCII
            if ASCII_PRINTABLE_MIN <= char_code <= ASCII_PRINTABLE_MAX:
                decoded += chr(char_code)
            elif char_code == 0 and decoded:  # Null terminator
                break
            elif strict:
                raise DecodingError(f"Non-printable character code: {char_code}")
            else:
                # Skip non-printable characters in non-strict mode
                logger.debug(f"Skipping non-printable character: {char_code}")
                continue

        return decoded

    def analyze_range(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """
        Analyze a date range and show statistics.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of contributions

        Raises:
            GitHubAPIError: If API request fails
        """
        logger.info(f"\n=== Analyzing {self.username} ===")
        logger.info(f"Date range: {start_date} to {end_date}\n")

        contributions = self.get_contribution_data(start_date, end_date)

        if not contributions:
            logger.error("Failed to fetch contribution data")
            return None

        # Statistics
        total_days = len(contributions)
        days_with_commits = sum(1 for c in contributions if c["count"] > 0)
        total_commits = sum(c["count"] for c in contributions)

        logger.info(f"Total days: {total_days}")
        logger.info(f"Days with commits: {days_with_commits}")
        logger.info(f"Total commits: {total_commits}")

        if days_with_commits > 0:
            logger.info(f"Average commits per active day: {total_commits / days_with_commits:.2f}")

        # Check if range is clear
        if days_with_commits == 0:
            logger.info("\n✓ Range is CLEAR - perfect for encoding!")
        else:
            logger.warning(f"\n⚠ Range has existing commits - encoding may interfere with existing data")

        # Show weekday-only stats
        weekday_contributions = self.filter_weekdays(contributions)
        weekday_days_with_commits = sum(1 for c in weekday_contributions if c["count"] > 0)

        logger.info(f"\nWeekdays only: {len(weekday_contributions)} days")
        logger.info(f"Weekdays with commits: {weekday_days_with_commits}")

        # Calculate capacity (2-bit encoding, minus start/end marker days)
        payload_days = max(0, len(weekday_contributions) - 2)
        capacity = payload_days * BITS_PER_CHUNK // BITS_PER_BYTE  # bytes

        logger.info(f"\n=== Encoding Capacity ===")
        logger.info(f"2-bit payload with darkest-green markers: {capacity} bytes ({capacity} characters)")
        logger.info(f"Approximate capacity: ~{capacity // 4} characters per month (weekdays only)")

        return contributions

    def decode_message(
        self,
        start_date: str,
        end_date: str,
        weekdays_only: bool = True,
        strict: bool = False
    ) -> Optional[str]:
        """
        Decode a hidden message from the contribution graph.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            weekdays_only: Only use weekdays for decoding
            strict: Raise error on non-printable characters

        Returns:
            Decoded message string

        Raises:
            GitHubAPIError: If API request fails
            DecodingError: If decoding fails
        """
        contributions = self.get_contribution_data(start_date, end_date)

        if not contributions:
            raise GitHubAPIError("Failed to fetch contribution data")

        if weekdays_only:
            contributions = self.filter_weekdays(contributions)

        # Convert marker-delimited payload to binary using 2-bit encoding
        binary = self.map_commits_to_bits(contributions)

        if not binary:
            raise DecodingError("No payload data to decode")

        logger.info(f"\nBinary data ({len(binary)} bits): {binary[:64]}{'...' if len(binary) > 64 else ''}")
        logger.info(f"Encoding: 2-bit payload with darkest-green start/end markers")

        # Convert to ASCII
        message = self.binary_to_ascii(binary, strict=strict)

        if not message:
            raise DecodingError("Decoded message is empty")

        return message


def main():
    """Main entry point for the decoder CLI."""
    parser = argparse.ArgumentParser(
        description="Decode messages from GitHub contribution graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a date range
  graph-stego-decode username --start 2024-01-01 --end 2024-01-31

  # Decode a message
  graph-stego-decode username --start 2024-01-01 --end 2024-02-28 --decode

  # Optionally use GitHub GraphQL API with a token
  graph-stego-decode username --token ghp_xxxxx --start 2024-01-01 --end 2024-02-28 --decode

  # Optionally set token via environment variable
  export GITHUB_TOKEN=ghp_xxxxx
  graph-stego-decode username --start 2024-01-01 --end 2024-02-28 --decode
        """
    )

    parser.add_argument("username", help="GitHub username to analyze")
    parser.add_argument("--token", help="GitHub personal access token (optional; uses GraphQL API)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--decode", action="store_true", help="Attempt to decode message")
    parser.add_argument("--all-days", action="store_true", help="Use all days (not just weekdays)")
    parser.add_argument("--strict", action="store_true", help="Strict mode: fail on non-printable characters")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Set logging level
    if args.quiet:
        logger.setLevel(logging.WARNING)
    elif args.verbose:
        logger.setLevel(logging.DEBUG)

    # Get optional token from arguments or environment
    token = args.token or os.environ.get('GITHUB_TOKEN')

    try:
        # Create decoder
        decoder = GitHubContributionDecoder(
            args.username,
            token=token
        )

        if args.decode:
            logger.info("\n=== Decoding Message ===")
            message = decoder.decode_message(
                args.start,
                args.end,
                weekdays_only=not args.all_days,
                strict=args.strict
            )

            if message:
                logger.info(f"\nDecoded message: {message}")
            else:
                logger.error("\nFailed to decode message")
                return 1
        else:
            decoder.analyze_range(args.start, args.end)

        return 0

    except (GitHubAPIError, DecodingError, ValueError) as e:
        logger.error(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130


if __name__ == "__main__":
    exit(main())
