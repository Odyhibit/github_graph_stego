#!/usr/bin/env python3
"""
Unit tests for GitHub Contribution Graph Steganography Decoder
"""

import unittest
from datetime import datetime
from unittest.mock import patch
from github_graph_stego.decoding import (
    GitHubContributionDecoder,
    DecodingError,
    GitHubAPIError
)


class TestBinaryToAscii(unittest.TestCase):
    """Test binary to ASCII conversion."""

    def setUp(self):
        self.decoder = GitHubContributionDecoder("testuser")

    def test_simple_binary(self):
        """Test converting simple binary to ASCII."""
        # 'Hi' = 01001000 01101001
        binary = "0100100001101001"
        result = self.decoder.binary_to_ascii(binary)
        self.assertEqual(result, "Hi")

    def test_single_character(self):
        """Test single character."""
        # 'A' = 01000001
        binary = "01000001"
        result = self.decoder.binary_to_ascii(binary)
        self.assertEqual(result, "A")

    def test_padding(self):
        """Test that padding works correctly."""
        # 'A' with 4 extra bits that will be padded
        binary = "010000011111"
        result = self.decoder.binary_to_ascii(binary)
        self.assertIn("A", result)

    def test_empty_binary(self):
        """Test empty binary raises error."""
        with self.assertRaises(DecodingError):
            self.decoder.binary_to_ascii("")

    def test_null_terminator(self):
        """Test null terminator stops decoding."""
        # 'Hi' followed by null byte
        binary = "010010000110100100000000"
        result = self.decoder.binary_to_ascii(binary)
        self.assertEqual(result, "Hi")

    def test_non_printable_strict_mode(self):
        """Test non-printable characters in strict mode."""
        # Binary for character code 1 (non-printable)
        binary = "00000001"
        with self.assertRaises(DecodingError):
            self.decoder.binary_to_ascii(binary, strict=True)

    def test_non_printable_non_strict(self):
        """Test non-printable characters in non-strict mode."""
        # Mix of printable and non-printable
        binary = "01000001" + "00000001" + "01000010"  # 'A' + \x01 + 'B'
        result = self.decoder.binary_to_ascii(binary, strict=False)
        # Should skip the non-printable character
        self.assertEqual(result, "AB")


class TestMapCommitsToBits(unittest.TestCase):
    """Test commit count to bit mapping."""

    def setUp(self):
        self.decoder = GitHubContributionDecoder("testuser")

    def test_commit_mapping(self):
        """Test 2-bit commit mapping with darkest-green markers."""
        contributions = [
            {"date": "2024-01-01", "count": 20},   # start marker
            {"date": "2024-01-02", "count": 0},    # -> 00
            {"date": "2024-01-03", "count": 1},    # -> 01
            {"date": "2024-01-04", "count": 5},    # -> 10
            {"date": "2024-01-05", "count": 10},   # -> 11
            {"date": "2024-01-06", "count": 20},   # end marker
        ]
        binary = self.decoder.map_commits_to_bits(contributions)
        self.assertEqual(binary, "00011011")

    def test_tolerance_ranges(self):
        """Test that tolerance ranges work correctly."""
        contributions = [
            {"date": "2024-01-01", "count": 20},   # start marker
            {"date": "2024-01-02", "count": 0},    # -> 00
            {"date": "2024-01-03", "count": 2},    # -> 01 (within 1-2)
            {"date": "2024-01-04", "count": 7},    # -> 10 (within 3-7)
            {"date": "2024-01-05", "count": 15},   # -> 11 (within 8-15)
            {"date": "2024-01-06", "count": 20},   # end marker
        ]
        binary = self.decoder.map_commits_to_bits(contributions)
        self.assertEqual(binary, "00011011")

    def test_zero_commits_decode_as_payload(self):
        """Test that zero commits decode as 00 between markers."""
        contributions = [
            {"date": "2024-01-01", "count": 20},   # start marker
            {"date": "2024-01-02", "count": 0},    # -> 00
            {"date": "2024-01-03", "count": 1},    # -> 01
            {"date": "2024-01-04", "count": 20},   # end marker
        ]
        binary = self.decoder.map_commits_to_bits(contributions)
        self.assertEqual(binary, "0001")

    def test_missing_markers_raise_error(self):
        """Test that marker-delimited data is required."""
        contributions = [
            {"date": "2024-01-01", "count": 0},
            {"date": "2024-01-02", "count": 1},
        ]
        with self.assertRaises(DecodingError):
            self.decoder.map_commits_to_bits(contributions)


class TestFilterWeekdays(unittest.TestCase):
    """Test weekday filtering."""

    def setUp(self):
        self.decoder = GitHubContributionDecoder("testuser")

    def test_filter_weekend(self):
        """Test that weekends are filtered out."""
        contributions = [
            {"date": "2024-01-05", "count": 1},  # Friday
            {"date": "2024-01-06", "count": 1},  # Saturday
            {"date": "2024-01-07", "count": 1},  # Sunday
            {"date": "2024-01-08", "count": 1},  # Monday
        ]
        filtered = self.decoder.filter_weekdays(contributions)
        dates = [c["date"] for c in filtered]
        self.assertEqual(dates, ["2024-01-05", "2024-01-08"])

    def test_all_weekdays(self):
        """Test that all weekdays are kept."""
        contributions = [
            {"date": "2024-01-01", "count": 1},  # Monday
            {"date": "2024-01-02", "count": 1},  # Tuesday
            {"date": "2024-01-03", "count": 1},  # Wednesday
            {"date": "2024-01-04", "count": 1},  # Thursday
            {"date": "2024-01-05", "count": 1},  # Friday
        ]
        filtered = self.decoder.filter_weekdays(contributions)
        self.assertEqual(len(filtered), 5)


class TestContributionFetching(unittest.TestCase):
    """Test contribution fetching sources."""

    def test_token_from_argument(self):
        """Test token passed as argument."""
        token = "ghp_test123"
        decoder = GitHubContributionDecoder("testuser", token=token)
        self.assertEqual(decoder.token, token)

    def test_no_token(self):
        """Test decoder works without token."""
        decoder = GitHubContributionDecoder("testuser")
        # Should not raise error, token can be None
        self.assertIsInstance(decoder, GitHubContributionDecoder)
        self.assertIsNone(decoder.token)

    @patch("github_graph_stego.decoding.GitHubContributionScraper")
    def test_public_scraper_without_token(self, mock_scraper_class):
        """Test decoder uses public scraping when no token is provided."""
        mock_scraper = mock_scraper_class.return_value
        mock_scraper.get_contribution_data.return_value = [
            {"date": "2024-01-01", "count": 20, "level": 4},
            {"date": "2024-01-02", "count": 0, "level": 0},
            {"date": "2024-01-03", "count": 20, "level": 4},
            {"date": "2024-01-04", "count": 1, "level": 1},
        ]

        decoder = GitHubContributionDecoder("testuser")
        contributions = decoder.get_contribution_data("2024-01-01", "2024-01-03")

        mock_scraper_class.assert_called_once_with("testuser")
        mock_scraper.get_contribution_data.assert_called_once_with(2024)
        self.assertEqual(
            contributions,
            [
                {"date": "2024-01-01", "count": 20},
                {"date": "2024-01-02", "count": 0},
                {"date": "2024-01-03", "count": 20},
            ]
        )

    @patch.object(GitHubContributionDecoder, "_get_graphql_contribution_data")
    def test_token_uses_graphql(self, mock_graphql):
        """Test decoder uses GraphQL when a token is provided."""
        mock_graphql.return_value = [{"date": "2024-01-01", "count": 0}]

        decoder = GitHubContributionDecoder("testuser", token="ghp_test123")
        contributions = decoder.get_contribution_data("2024-01-01", "2024-01-01")

        mock_graphql.assert_called_once_with("2024-01-01", "2024-01-01", 3)
        self.assertEqual(contributions, [{"date": "2024-01-01", "count": 0}])


class TestRoundtrip(unittest.TestCase):
    """Test encoder/decoder roundtrip."""

    def test_message_roundtrip(self):
        """Test that encoded message can be decoded."""
        from github_graph_stego.encoding import GitHubContributionEncoder

        # Create encoder and decoder
        encoder = GitHubContributionEncoder()
        decoder = GitHubContributionDecoder("testuser")

        # Original message
        message = "Test"

        # Encode: message -> binary -> commit plan
        binary = encoder.message_to_binary(message)
        start_date = datetime(2024, 1, 1)
        commit_plan = encoder.binary_to_commit_plan(binary, start_date, weekdays_only=False)

        # Simulate contributions from commit plan
        contributions = [
            {"date": date, "count": count}
            for date, count in commit_plan
        ]

        # Decode: contributions -> binary -> message
        decoded_binary = decoder.map_commits_to_bits(contributions)
        decoded_message = decoder.binary_to_ascii(decoded_binary)

        self.assertEqual(decoded_message, message)

    def test_complex_messages(self):
        """Test roundtrip with various messages."""
        from github_graph_stego.encoding import GitHubContributionEncoder

        test_messages = [
            "A",
            "Hello",
            "CTF{flag}",
            "Test123",
            "!@#$%",
        ]

        for message in test_messages:
            with self.subTest(message=message):
                encoder = GitHubContributionEncoder()
                decoder = GitHubContributionDecoder("testuser")

                binary = encoder.message_to_binary(message)
                commit_plan = encoder.binary_to_commit_plan(
                    binary,
                    datetime(2024, 1, 1),
                    weekdays_only=False
                )

                contributions = [
                    {"date": date, "count": count}
                    for date, count in commit_plan
                ]

                decoded_binary = decoder.map_commits_to_bits(contributions)
                decoded_message = decoder.binary_to_ascii(decoded_binary)

                self.assertEqual(decoded_message, message)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_very_long_message(self):
        """Test encoding/decoding a long message."""
        from github_graph_stego.encoding import GitHubContributionEncoder

        encoder = GitHubContributionEncoder()
        decoder = GitHubContributionDecoder("testuser")

        message = "A" * 100
        binary = encoder.message_to_binary(message)
        commit_plan = encoder.binary_to_commit_plan(
            binary,
            datetime(2024, 1, 1),
            weekdays_only=False
        )

        contributions = [
            {"date": date, "count": count}
            for date, count in commit_plan
        ]

        decoded_binary = decoder.map_commits_to_bits(contributions)
        decoded_message = decoder.binary_to_ascii(decoded_binary)

        self.assertEqual(decoded_message, message)

    def test_all_same_character(self):
        """Test message with all same characters."""
        from github_graph_stego.encoding import GitHubContributionEncoder

        encoder = GitHubContributionEncoder()
        decoder = GitHubContributionDecoder("testuser")

        message = "AAAA"
        binary = encoder.message_to_binary(message)
        commit_plan = encoder.binary_to_commit_plan(
            binary,
            datetime(2024, 1, 1),
            weekdays_only=False
        )

        contributions = [
            {"date": date, "count": count}
            for date, count in commit_plan
        ]

        decoded_binary = decoder.map_commits_to_bits(contributions)
        decoded_message = decoder.binary_to_ascii(decoded_binary)

        self.assertEqual(decoded_message, message)


if __name__ == '__main__':
    unittest.main()
