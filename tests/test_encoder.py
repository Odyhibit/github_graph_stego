#!/usr/bin/env python3
"""
Unit tests for GitHub Contribution Graph Steganography Encoder
"""

import unittest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from github_graph_stego.encoding import (
    GitHubContributionEncoder,
    EncodingError,
    MARKER_COMMITS
)


class TestMessageToBinary(unittest.TestCase):
    """Test message to binary conversion."""

    def setUp(self):
        self.encoder = GitHubContributionEncoder()

    def test_simple_message(self):
        """Test converting a simple message to binary."""
        message = "Hi"
        binary = self.encoder.message_to_binary(message)
        # 'H' = 72 = 01001000, 'i' = 105 = 01101001
        expected = "0100100001101001"
        self.assertEqual(binary, expected)

    def test_single_character(self):
        """Test single character conversion."""
        message = "A"
        binary = self.encoder.message_to_binary(message)
        # 'A' = 65 = 01000001
        expected = "01000001"
        self.assertEqual(binary, expected)

    def test_empty_message(self):
        """Test that empty message raises error."""
        with self.assertRaises(EncodingError):
            self.encoder.message_to_binary("")

    def test_special_characters(self):
        """Test special characters."""
        message = "!@#"
        binary = self.encoder.message_to_binary(message)
        # '!' = 33, '@' = 64, '#' = 35
        self.assertEqual(len(binary), 24)  # 3 chars * 8 bits

    def test_numbers(self):
        """Test numeric characters."""
        message = "123"
        binary = self.encoder.message_to_binary(message)
        # '1' = 49, '2' = 50, '3' = 51
        self.assertEqual(len(binary), 24)


class TestBinaryToCommitPlan(unittest.TestCase):
    """Test binary to commit plan conversion."""

    def setUp(self):
        self.encoder = GitHubContributionEncoder()

    def test_simple_binary(self):
        """Test 2-bit encoding with darkest-green markers."""
        binary = "00011011"  # Four 2-bit chunks
        start_date = datetime(2024, 1, 1)
        plan = self.encoder.binary_to_commit_plan(binary, start_date, weekdays_only=False)

        # Expected: marker, 00->0, 01->1, 10->5, 11->10, marker
        expected_counts = [MARKER_COMMITS, 0, 1, 5, 10, MARKER_COMMITS]
        actual_counts = [count for _, count in plan]
        self.assertEqual(actual_counts, expected_counts)

    def test_weekdays_only(self):
        """Test weekday-only encoding skips weekends."""
        binary = "0001"  # Two 2-bit chunks
        start_date = datetime(2024, 1, 5)  # Friday
        plan = self.encoder.binary_to_commit_plan(binary, start_date, weekdays_only=True)

        dates = [date for date, _ in plan]
        # Should include start marker, two payload days, and end marker.
        self.assertEqual(dates, ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10"])

    def test_invalid_binary(self):
        """Test invalid binary string raises error."""
        with self.assertRaises(ValueError):
            self.encoder.binary_to_commit_plan("012", datetime.now())

    def test_empty_binary(self):
        """Test empty binary string raises error."""
        with self.assertRaises(ValueError):
            self.encoder.binary_to_commit_plan("", datetime.now())


class TestValidateEncoding(unittest.TestCase):
    """Test encoding validation."""

    def setUp(self):
        self.encoder = GitHubContributionEncoder()

    def test_valid_encoding(self):
        """Test validation of correct encoding."""
        message = "Hi"
        binary = self.encoder.message_to_binary(message)
        plan = self.encoder.binary_to_commit_plan(binary, datetime(2024, 1, 1), weekdays_only=False)
        result = self.encoder.validate_encoding(message, plan)
        self.assertTrue(result)

    def test_roundtrip(self):
        """Test message -> binary -> plan -> validation."""
        messages = ["Test", "CTF{flag}", "Hello World!", "123"]
        for message in messages:
            with self.subTest(message=message):
                binary = self.encoder.message_to_binary(message)
                plan = self.encoder.binary_to_commit_plan(binary, datetime(2024, 1, 1), weekdays_only=False)
                self.assertTrue(self.encoder.validate_encoding(message, plan))


class TestConfiguration(unittest.TestCase):
    """Test configuration loading and handling."""

    def test_default_config(self):
        """Test default configuration."""
        encoder = GitHubContributionEncoder()
        self.assertEqual(encoder.config["author_name"], "Steganographer")
        self.assertTrue(encoder.config["weekdays_only"])

    def test_custom_config(self):
        """Test custom configuration."""
        config = {
            "author_name": "Custom Author",
            "stealth_mode": True
        }
        encoder = GitHubContributionEncoder(config=config)
        self.assertEqual(encoder.config["author_name"], "Custom Author")
        self.assertTrue(encoder.config["stealth_mode"])


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def setUp(self):
        """Create temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_encode_dry_run(self):
        """Test encoding in dry run mode."""
        encoder = GitHubContributionEncoder(self.test_dir)
        start_date = datetime(2024, 1, 1)
        plan = encoder.encode_message(
            "Test",
            start_date,
            dry_run=True,
            validate=True
        )
        self.assertIsNotNone(plan)
        self.assertGreater(len(plan), 0)

    def test_full_encoding_workflow(self):
        """Test full encoding workflow without pushing."""
        encoder = GitHubContributionEncoder(self.test_dir)
        start_date = datetime(2024, 1, 1)

        # Encode message
        plan = encoder.encode_message(
            "Hi",
            start_date,
            weekdays_only=False,
            validate=True,
            dry_run=False
        )

        # Check that git repo was created
        git_dir = Path(self.test_dir) / '.git'
        self.assertTrue(git_dir.exists())

        # Check commit plan
        self.assertEqual(len(plan), 10)  # "Hi" = 8 payload chunks + 2 markers


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_long_message(self):
        """Test encoding a long message."""
        encoder = GitHubContributionEncoder()
        message = "A" * 100
        binary = encoder.message_to_binary(message)
        self.assertEqual(len(binary), 800)  # 100 chars * 8 bits

    def test_special_ascii_characters(self):
        """Test encoding special ASCII characters."""
        encoder = GitHubContributionEncoder()
        message = "Tab:\tNewline:\nQuote:\"Backslash:\\"
        binary = encoder.message_to_binary(message)
        self.assertGreater(len(binary), 0)

    def test_stealth_mode_randomization(self):
        """Test that stealth mode produces different commit counts."""
        encoder = GitHubContributionEncoder()
        binary = "11111111"  # All same pattern
        start_date = datetime(2024, 1, 1)

        # Without stealth mode
        plan1 = encoder.binary_to_commit_plan(binary, start_date, weekdays_only=False, stealth_mode=False)
        counts1 = [count for _, count in plan1]

        # With stealth mode (multiple runs should produce different results)
        plan2 = encoder.binary_to_commit_plan(binary, start_date, weekdays_only=False, stealth_mode=True)
        counts2 = [count for _, count in plan2]

        # Stealth mode should produce different counts (probabilistically)
        # We can't guarantee they're different in every run, but they should be close to original
        for c1, c2 in zip(counts1, counts2):
            self.assertLessEqual(abs(c1 - c2), max(1, int(c1 * 0.3)))  # Within 30%


if __name__ == '__main__':
    unittest.main()
