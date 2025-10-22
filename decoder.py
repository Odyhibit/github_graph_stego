#!/usr/bin/env python3
"""
GitHub Contribution Graph Steganography Decoder
Extracts hidden messages from GitHub contribution patterns
"""

import requests
import json
from datetime import datetime, timedelta
import argparse
import sys


class GitHubContributionDecoder:
    def __init__(self, username, token=None):
        """
        Initialize decoder with GitHub username and optional API token

        Args:
            username: GitHub username to analyze
            token: GitHub personal access token (optional but recommended for rate limits)
        """
        self.username = username
        self.token = token
        self.api_url = "https://api.github.com/graphql"

        # Color level to commit count mapping (reverse of encoder)
        self.commit_to_level = {
            0: 0,  # No contribution
            1: 1,  # Light green
            5: 2,  # Medium-light green
            10: 3,  # Medium-dark green
            20: 4  # Darkest green
        }

    def get_contribution_data(self, start_date, end_date):
        """
        Fetch contribution data from GitHub GraphQL API

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of dicts with 'date' and 'count' keys
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

        if self.token:
            headers["Authorization"] = f"token {self.token}"

        try:
            response = requests.post(
                self.api_url,
                json={"query": query, "variables": variables},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                print(f"GraphQL Error: {data['errors']}")
                return None

            # Flatten the nested structure
            contributions = []
            weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            for week in weeks:
                for day in week["contributionDays"]:
                    contributions.append({
                        "date": day["date"],
                        "count": day["contributionCount"]
                    })

            return contributions

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def filter_weekdays(self, contributions):
        """
        Filter contributions to only include weekdays (Mon-Fri)

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
        return weekday_contributions

    def map_commits_to_bits(self, contributions, use_zero_level=False):
        """
        Map commit counts to bit patterns

        Args:
            contributions: List of contribution dicts
            use_zero_level: If True, use 5 levels (3 bits). If False, use 4 levels (2 bits)

        Returns:
            Binary string
        """
        binary = ""

        for contrib in contributions:
            count = contrib["count"]

            # Find the closest matching level
            if use_zero_level:
                # 3-bit encoding with 5 levels
                if count == 0:
                    binary += "000"
                elif count <= 2:
                    binary += "001"
                elif count <= 7:
                    binary += "010"
                elif count <= 15:
                    binary += "011"
                else:
                    binary += "100"
            else:
                # 2-bit encoding with 4 levels (ignoring zero)
                if count == 0:
                    continue  # Skip days with no commits
                elif count <= 2:
                    binary += "00"
                elif count <= 7:
                    binary += "01"
                elif count <= 15:
                    binary += "10"
                else:
                    binary += "11"

        return binary

    def binary_to_ascii(self, binary_string):
        """
        Convert binary string to ASCII text

        Args:
            binary_string: String of 0s and 1s

        Returns:
            Decoded ASCII string
        """
        # Pad to multiple of 8
        padding = (8 - len(binary_string) % 8) % 8
        binary_string += "0" * padding

        decoded = ""
        for i in range(0, len(binary_string), 8):
            byte = binary_string[i:i + 8]
            char_code = int(byte, 2)
            # Only add printable ASCII characters
            if 32 <= char_code <= 126:
                decoded += chr(char_code)
            elif char_code == 0 and decoded:  # Null terminator
                break

        return decoded

    def analyze_range(self, start_date, end_date):
        """
        Analyze a date range and show statistics

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        print(f"\n=== Analyzing {self.username} ===")
        print(f"Date range: {start_date} to {end_date}\n")

        contributions = self.get_contribution_data(start_date, end_date)

        if not contributions:
            print("Failed to fetch contribution data")
            return

        # Statistics
        total_days = len(contributions)
        days_with_commits = sum(1 for c in contributions if c["count"] > 0)
        total_commits = sum(c["count"] for c in contributions)

        print(f"Total days: {total_days}")
        print(f"Days with commits: {days_with_commits}")
        print(f"Total commits: {total_commits}")

        if days_with_commits > 0:
            print(f"Average commits per active day: {total_commits / days_with_commits:.2f}")

        # Check if range is clear
        if days_with_commits == 0:
            print("\n✓ Range is CLEAR - perfect for encoding!")
        else:
            print(f"\n⚠ Range has existing commits - encoding may interfere with existing data")

        # Show weekday-only stats
        weekday_contributions = self.filter_weekdays(contributions)
        weekday_commits = sum(c["count"] for c in weekday_contributions if c["count"] > 0)

        print(f"\nWeekdays only: {len(weekday_contributions)} days")
        print(f"Weekday commits: {weekday_commits}")

        # Calculate capacity
        capacity_2bit = len(weekday_contributions) * 2 // 8  # bytes
        capacity_3bit = len(weekday_contributions) * 3 // 8  # bytes

        print(f"\n=== Encoding Capacity ===")
        print(f"2-bit encoding (4 levels): {capacity_2bit} bytes ({capacity_2bit} characters)")
        print(f"3-bit encoding (5 levels): {capacity_3bit} bytes ({capacity_3bit} characters)")

        return contributions

    def decode_message(self, start_date, end_date, weekdays_only=True, use_zero_level=False):
        """
        Decode a hidden message from the contribution graph

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            weekdays_only: Only use weekdays for decoding
            use_zero_level: Use 5 levels (3-bit) instead of 4 levels (2-bit)

        Returns:
            Decoded message string
        """
        contributions = self.get_contribution_data(start_date, end_date)

        if not contributions:
            return None

        if weekdays_only:
            contributions = self.filter_weekdays(contributions)

        # Convert to binary
        binary = self.map_commits_to_bits(contributions, use_zero_level)

        if not binary:
            print("No data to decode")
            return None

        print(f"\nBinary data ({len(binary)} bits): {binary[:64]}{'...' if len(binary) > 64 else ''}")

        # Convert to ASCII
        message = self.binary_to_ascii(binary)

        return message


def main():
    parser = argparse.ArgumentParser(
        description="Decode messages from GitHub contribution graphs"
    )
    parser.add_argument("username", help="GitHub username to analyze")
    parser.add_argument("--token", help="GitHub personal access token (optional)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--decode", action="store_true", help="Attempt to decode message")
    parser.add_argument("--all-days", action="store_true", help="Use all days (not just weekdays)")
    parser.add_argument("--use-zero", action="store_true", help="Use 5-level encoding (3 bits per day)")

    args = parser.parse_args()

    decoder = GitHubContributionDecoder(args.username, args.token)

    if args.decode:
        print(f"\n=== Decoding Message ===")
        message = decoder.decode_message(
            args.start,
            args.end,
            weekdays_only=not args.all_days,
            use_zero_level=args.use_zero
        )

        if message:
            print(f"\nDecoded message: {message}")
        else:
            print("\nFailed to decode message")
    else:
        decoder.analyze_range(args.start, args.end)


if __name__ == "__main__":
    main()