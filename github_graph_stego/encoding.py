#!/usr/bin/env python3
"""
GitHub Contribution Graph Steganography Encoder

Encodes messages into GitHub contribution patterns by creating backdated commits.
"""

import os
import subprocess
import argparse
import json
import logging
import random
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import tempfile
import shutil


# Constants
BITS_PER_BYTE = 8
BITS_PER_CHUNK = 2  # 2-bit encoding for 4 payload states

# Commit count mapping for payload levels. The darkest green level is reserved
# as a start/end marker, so empty days carry the 00 payload.
# - Level 0 (00): Empty/gray - 0 commits
# - Level 1 (01): Light green - 1 commit
# - Level 2 (10): Medium-light green - 5 commits
# - Level 3 (11): Medium-dark green - 10 commits
COMMIT_LEVELS = {
    0: 0,   # Empty/gray (00)
    1: 1,   # Light green (01)
    2: 5,   # Medium-light green (10)
    3: 10   # Medium-dark green (11)
}
MARKER_COMMITS = 20  # Darkest green, reserved for start/end markers

ASCII_PRINTABLE_MIN = 32
ASCII_PRINTABLE_MAX = 126

# Default configuration
DEFAULT_CONFIG = {
    "author_name": "Steganographer",
    "author_email": "stego@example.com",
    "commit_message_template": "Update",
    "weekdays_only": True,
    "stealth_mode": False,
    "time_randomization": False
}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class EncodingError(Exception):
    """Custom exception for encoding errors."""
    pass


class GitCommandError(Exception):
    """Custom exception for git command failures."""
    pass


class GitHubContributionEncoder:
    """Encodes messages into GitHub contribution graphs using steganography."""

    def __init__(self, repo_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize encoder.

        Args:
            repo_path: Path to git repository (will create temp repo if None)
            config: Configuration dictionary (uses defaults if None)

        Raises:
            ValueError: If repo_path exists but is not a valid directory
        """
        self.repo_path = repo_path
        self.temp_repo = repo_path is None
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        if repo_path and not Path(repo_path).is_dir() and Path(repo_path).exists():
            raise ValueError(f"Invalid repository path: {repo_path}")

        # Use 2-bit payload encoding plus darkest-green start/end markers
        self.level_to_commits = COMMIT_LEVELS

    def _run_git_command(
        self,
        cmd: List[str],
        silent: bool = True,
        env: Optional[Dict[str, str]] = None,
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Helper to run git commands with consistent error handling.

        Args:
            cmd: Git command as list of strings
            silent: If True, suppress stdout/stderr
            env: Optional environment variables
            check: If True, raise exception on non-zero exit code

        Returns:
            CompletedProcess object

        Raises:
            GitCommandError: If command fails and check=True
        """
        output = subprocess.DEVNULL if silent else None
        try:
            return subprocess.run(
                cmd,
                cwd=self.repo_path,
                stdout=output,
                stderr=output if silent else subprocess.PIPE,
                check=check,
                env=env,
                text=True
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            raise GitCommandError(f"Git command failed: {' '.join(cmd)}\n{error_msg}")

    @staticmethod
    def load_config(config_path: str = "config.json") -> Dict[str, Any]:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary

        Raises:
            ValueError: If config file is invalid JSON
        """
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        return {}

    def message_to_binary(self, message: str) -> str:
        """
        Convert message to binary string.

        Args:
            message: String to encode

        Returns:
            Binary string (e.g., "01001000")

        Raises:
            EncodingError: If message contains non-ASCII characters
        """
        if not message:
            raise EncodingError("Cannot encode empty message")

        binary = ""
        for char in message:
            try:
                # Convert each character to 8-bit binary
                binary += format(ord(char), '08b')
            except (ValueError, OverflowError) as e:
                raise EncodingError(f"Cannot encode character '{char}': {e}")
        return binary

    def binary_to_commit_plan(
        self,
        binary_string: str,
        start_date: datetime,
        weekdays_only: bool = True,
        stealth_mode: bool = False
    ) -> List[Tuple[str, int]]:
        """
        Convert binary string to a plan of (date, commit_count) tuples.

        Args:
            binary_string: String of 0s and 1s
            start_date: Starting date
            weekdays_only: Only use weekdays for encoding
            stealth_mode: Add randomization to commit counts for stealth

        Returns:
            List of (date_string, commit_count) tuples

        Raises:
            ValueError: If binary string is invalid
        """
        if not binary_string or not all(c in '01' for c in binary_string):
            raise ValueError("Invalid binary string")

        # Split binary into 2-bit chunks (4 payload states)
        chunks = [binary_string[i:i + BITS_PER_CHUNK]
                  for i in range(0, len(binary_string), BITS_PER_CHUNK)]

        commit_plan: List[Tuple[str, int]] = []
        current_date = start_date

        while weekdays_only and current_date.weekday() >= 5:  # Skip weekends
            current_date += timedelta(days=1)

        commit_plan.append((current_date.strftime('%Y-%m-%d'), MARKER_COMMITS))
        current_date += timedelta(days=1)

        for chunk in chunks:
            # Pad last chunk if needed
            if len(chunk) < BITS_PER_CHUNK:
                chunk = chunk.ljust(BITS_PER_CHUNK, '0')

            # Find next valid date (weekday if required)
            while weekdays_only and current_date.weekday() >= 5:  # Skip weekends
                current_date += timedelta(days=1)

            # Convert chunk to level
            level = int(chunk, 2)
            commit_count = self.level_to_commits[level]

            # Apply stealth mode randomization
            if stealth_mode and commit_count > 0:
                # Add ±20% randomization to commit count
                variance = max(1, int(commit_count * 0.2))
                commit_count += random.randint(-variance, variance)
                commit_count = max(1, commit_count)  # Ensure at least 1 commit

            # Format date as YYYY-MM-DD
            date_str = current_date.strftime('%Y-%m-%d')
            commit_plan.append((date_str, commit_count))

            # Move to next day
            current_date += timedelta(days=1)

        while weekdays_only and current_date.weekday() >= 5:  # Skip weekends
            current_date += timedelta(days=1)

        commit_plan.append((current_date.strftime('%Y-%m-%d'), MARKER_COMMITS))

        return commit_plan

    def init_repo(self) -> str:
        """
        Initialize git repository (create temp if needed).

        Returns:
            Path to repository

        Raises:
            GitCommandError: If git initialization fails
        """
        if self.temp_repo:
            # Create temporary directory
            self.repo_path = tempfile.mkdtemp(prefix='github_stego_')
            logger.info(f"Created temporary repository: {self.repo_path}")

        # Initialize git repo
        self._run_git_command(['git', 'init'])
        self._run_git_command(['git', 'config', 'user.name', self.config.get("author_name", "Steganographer")])
        self._run_git_command(['git', 'config', 'user.email', self.config.get("author_email", "stego@example.com")])

        # Create initial file
        readme_path = Path(self.repo_path) / 'README.md'
        with open(readme_path, 'w') as f:
            f.write('# Steganography Repository\n\nThis repository contains encoded data.\n')

        self._run_git_command(['git', 'add', 'README.md'])
        self._run_git_command(['git', 'commit', '-m', 'Initial commit'])

        return self.repo_path

    def create_commit(
        self,
        date_str: str,
        message: str,
        author_name: str = "Steganographer",
        author_email: str = "stego@example.com",
        time_randomization: bool = False
    ) -> None:
        """
        Create a single commit with a specific date.

        Args:
            date_str: Date string (YYYY-MM-DD)
            message: Commit message
            author_name: Git author name
            author_email: Git author email
            time_randomization: If True, randomize commit times for stealth

        Raises:
            GitCommandError: If commit creation fails
        """
        # Set the time - randomize if stealth mode
        if time_randomization:
            hour = random.randint(9, 18)  # Business hours
            minute = random.randint(0, 59)
            datetime_str = f"{date_str}T{hour:02d}:{minute:02d}:00"
        else:
            datetime_str = f"{date_str}T12:00:00"

        # Create environment with custom dates
        env = os.environ.copy()
        env['GIT_AUTHOR_DATE'] = datetime_str
        env['GIT_COMMITTER_DATE'] = datetime_str
        env['GIT_COMMITTER_NAME'] = author_name
        env['GIT_COMMITTER_EMAIL'] = author_email

        # Make a trivial change to the data file
        data_file = Path(self.repo_path) / 'data.txt'
        with open(data_file, 'a') as f:
            f.write(f"{datetime_str}\n")

        # Stage and commit
        self._run_git_command(['git', 'add', 'data.txt'])
        self._run_git_command(
            ['git', 'commit', '--allow-empty', '-m', message,
             '--author', f'{author_name} <{author_email}>'],
            env=env
        )

    def validate_encoding(self, message: str, commit_plan: List[Tuple[str, int]]) -> bool:
        """
        Validate that the commit plan will correctly decode to the original message.

        Args:
            message: Original message
            commit_plan: Generated commit plan

        Returns:
            True if validation succeeds

        Raises:
            EncodingError: If validation fails
        """
        # Reconstruct binary from commit plan
        reconstructed_binary = ""
        payload_plan = commit_plan
        if len(commit_plan) >= 2 and commit_plan[0][1] == MARKER_COMMITS and commit_plan[-1][1] == MARKER_COMMITS:
            payload_plan = commit_plan[1:-1]

        for _, commit_count in payload_plan:
            # Find closest level
            closest_level = min(
                self.level_to_commits.keys(),
                key=lambda k: abs(self.level_to_commits[k] - commit_count)
            )
            # Convert level back to binary (2-bit)
            reconstructed_binary += format(closest_level, f'0{BITS_PER_CHUNK}b')

        # Convert back to text
        original_binary = self.message_to_binary(message)

        # Trim to same length (commit plan might have padding)
        reconstructed_binary = reconstructed_binary[:len(original_binary)]

        if reconstructed_binary != original_binary:
            raise EncodingError("Validation failed: encoding does not correctly represent message")

        logger.info("Validation successful: encoding will correctly decode")
        return True

    def encode_message(
        self,
        message: str,
        start_date: datetime,
        weekdays_only: Optional[bool] = None,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
        commit_message: Optional[str] = None,
        stealth_mode: Optional[bool] = None,
        time_randomization: Optional[bool] = None,
        validate: bool = True,
        dry_run: bool = False
    ) -> List[Tuple[str, int]]:
        """
        Encode a message into the git repository.

        Args:
            message: Message to encode
            start_date: Starting date
            weekdays_only: Only use weekdays (uses config default if None)
            author_name: Git author name (uses config default if None)
            author_email: Git author email (uses config default if None)
            commit_message: Template for commit messages (uses config default if None)
            stealth_mode: Enable stealth mode (uses config default if None)
            time_randomization: Randomize commit times (uses config default if None)
            validate: Validate encoding before committing
            dry_run: If True, only show what would be done without creating commits

        Returns:
            Commit plan (list of date, count tuples)

        Raises:
            EncodingError: If encoding or validation fails
            GitCommandError: If git operations fail
        """
        # Use config defaults if not specified
        weekdays_only = weekdays_only if weekdays_only is not None else self.config.get("weekdays_only", True)
        author_name = author_name or self.config.get("author_name", "Steganographer")
        author_email = author_email or self.config.get("author_email", "stego@example.com")
        commit_message = commit_message or self.config.get("commit_message_template", "Update")
        stealth_mode = stealth_mode if stealth_mode is not None else self.config.get("stealth_mode", False)
        time_randomization = time_randomization if time_randomization is not None else self.config.get("time_randomization", False)

        # Convert message to binary
        logger.info(f"Encoding message: {message}")
        binary = self.message_to_binary(message)
        logger.info(f"Binary representation ({len(binary)} bits): {binary[:64]}{'...' if len(binary) > 64 else ''}")

        # Create commit plan
        commit_plan = self.binary_to_commit_plan(binary, start_date, weekdays_only, stealth_mode)

        logger.info(f"Commit plan: {len(commit_plan)} days")
        logger.info(f"Date range: {commit_plan[0][0]} to {commit_plan[-1][0]}")
        logger.info(f"Total commits to create: {sum(count for _, count in commit_plan)}")
        logger.info(f"Encoding mode: 2-bit payload with darkest-green start/end markers")

        if stealth_mode:
            logger.info("Stealth mode: ENABLED (commit counts randomized)")
        if time_randomization:
            logger.info("Time randomization: ENABLED")

        # Validate encoding if requested
        if validate and not stealth_mode:  # Skip validation in stealth mode due to randomization
            self.validate_encoding(message, commit_plan)

        if dry_run:
            logger.info("\nDRY RUN MODE - No commits will be created")
            logger.info("\nCommit plan preview (first 10 days):")
            for date_str, count in commit_plan[:10]:
                logger.info(f"  {date_str}: {count} commits")
            if len(commit_plan) > 10:
                logger.info(f"  ... and {len(commit_plan) - 10} more days")
            return commit_plan

        # Initialize repo if needed
        repo_git_path = Path(self.repo_path or '.') / '.git'
        if not repo_git_path.exists():
            self.init_repo()

        # Create commits
        logger.info("\nCreating commits...")
        total_commits = sum(count for _, count in commit_plan)
        commits_created = 0
        progress_interval = max(1, total_commits // 10)

        for i, (date_str, commit_count) in enumerate(commit_plan):
            for j in range(commit_count):
                msg = f"{commit_message} {i}-{j}"
                self.create_commit(date_str, msg, author_name, author_email, time_randomization)
                commits_created += 1
                if commits_created % progress_interval == 0 or commits_created == total_commits:
                    logger.info(f"Encoding progress: {commits_created}/{total_commits} commits")

        logger.info(f"\nEncoding complete! Created {total_commits} commits")
        logger.info(f"Repository: {self.repo_path}")

        return commit_plan

    def add_remote(self, remote_url: str, remote_name: str = 'origin') -> None:
        """
        Add a remote to the repository.

        Args:
            remote_url: GitHub repository URL
            remote_name: Name for the remote (default: origin)

        Raises:
            GitCommandError: If adding remote fails
        """
        try:
            # Remove existing remote if present
            self._run_git_command(
                ['git', 'remote', 'remove', remote_name],
                check=False
            )
        except GitCommandError:
            pass

        self._run_git_command(['git', 'remote', 'add', remote_name, remote_url])
        logger.info(f"Added remote '{remote_name}': {remote_url}")

    def push_to_github(self, branch: str = 'main', force: bool = True) -> None:
        """
        Push commits to GitHub.

        Args:
            branch: Branch name to push
            force: Use force push (needed for backdated commits)

        Raises:
            GitCommandError: If push fails
        """
        logger.info(f"Pushing to GitHub (branch: {branch})...")

        # Rename branch if needed
        self._run_git_command(['git', 'branch', '-M', branch])

        # Push
        cmd = ['git', 'push', 'origin', branch]
        if force:
            cmd.insert(2, '-f')

        try:
            self._run_git_command(cmd, silent=False)
            logger.info("Successfully pushed to GitHub!")
            logger.info("\nIMPORTANT: It may take a few minutes for GitHub to update the contribution graph.")
        except GitCommandError:
            logger.error("Push failed. Make sure you have:")
            logger.error("  1. Created the repository on GitHub")
            logger.error("  2. Set up authentication (SSH key or token)")
            logger.error("  3. Added the remote with --remote flag")
            raise

    def cleanup(self) -> None:
        """
        Clean up temporary repository.

        Raises:
            OSError: If cleanup fails
        """
        if self.temp_repo and self.repo_path and Path(self.repo_path).exists():
            try:
                shutil.rmtree(self.repo_path)
                logger.info(f"Cleaned up temporary repository: {self.repo_path}")
            except OSError as e:
                logger.error(f"Failed to clean up temporary repository: {e}")
                raise


def main():
    """Main entry point for the encoder CLI."""
    parser = argparse.ArgumentParser(
        description="Encode messages into GitHub contribution graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encode a message starting Jan 1, 2024 (creates temp repo)
  graph-stego-encode "CTF{hidden_flag}" --start 2024-01-01

  # Encode into existing repository
  graph-stego-encode "CTF{hidden_flag}" --start 2024-01-01 --repo ./my-repo

  # Add remote and push to GitHub
  graph-stego-encode "CTF{hidden_flag}" --start 2024-01-01 \\
    --remote git@github.com:username/repo.git --push

  # Use stealth mode with time randomization
  graph-stego-encode "Secret" --start 2024-01-01 --stealth --randomize-time

  # Dry run to preview commit plan
  graph-stego-encode "Test" --start 2024-01-01 --dry-run
        """
    )

    parser.add_argument("message", help="Message to encode")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--repo", help="Path to git repository (creates temp if not specified)")
    parser.add_argument("--remote", help="GitHub repository URL (e.g., git@github.com:user/repo.git)")
    parser.add_argument("--push", action="store_true", help="Push to GitHub after encoding")
    parser.add_argument("--branch", default="main", help="Branch name (default: main)")
    parser.add_argument("--all-days", action="store_true", help="Use all days (not just weekdays)")
    parser.add_argument("--author", help="Git author name")
    parser.add_argument("--email", help="Git author email")
    parser.add_argument("--commit-msg", help="Commit message template")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--stealth", action="store_true", help="Enable stealth mode (randomize commit counts)")
    parser.add_argument("--randomize-time", action="store_true", help="Randomize commit times")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation step")
    parser.add_argument("--dry-run", action="store_true", help="Preview commit plan without creating commits")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Set logging level
    if args.quiet:
        logger.setLevel(logging.WARNING)
    elif args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load configuration
    config = {}
    if args.config:
        try:
            config = GitHubContributionEncoder.load_config(args.config)
        except (ValueError, FileNotFoundError) as e:
            logger.error(f"Error loading config: {e}")
            return 1

    # Override config with command-line arguments
    if args.stealth:
        config['stealth_mode'] = True
    if args.randomize_time:
        config['time_randomization'] = True
    if args.author:
        config['author_name'] = args.author
    if args.email:
        config['author_email'] = args.email
    if args.commit_msg:
        config['commit_message_template'] = args.commit_msg

    # Create encoder
    try:
        encoder = GitHubContributionEncoder(args.repo, config)
    except ValueError as e:
        logger.error(f"Error creating encoder: {e}")
        return 1

    try:
        # Parse start date
        try:
            start_date = datetime.strptime(args.start, '%Y-%m-%d')
        except ValueError:
            logger.error(f"Invalid date format: {args.start}. Use YYYY-MM-DD")
            return 1

        # Encode the message
        commit_plan = encoder.encode_message(
            args.message,
            start_date,
            weekdays_only=not args.all_days,
            validate=not args.no_validate,
            dry_run=args.dry_run
        )

        if args.dry_run:
            return 0

        # Add remote if specified
        if args.remote:
            encoder.add_remote(args.remote)

        # Push if requested
        if args.push:
            if not args.remote:
                logger.error("Cannot push: no remote specified (use --remote)")
                return 1
            encoder.push_to_github(args.branch, force=True)
        else:
            logger.info("\nTo push to GitHub:")
            if args.remote:
                logger.info(f"  cd {encoder.repo_path}")
                logger.info(f"  git push -f origin {args.branch}")
            else:
                logger.info("  1. Add remote: git remote add origin <github-url>")
                logger.info(f"  2. Push: git push -f origin {args.branch}")

        # Show decoder command
        logger.info("\nTo decode this message:")
        end_date = start_date + timedelta(days=len(commit_plan))
        decoder_cmd = f"graph-stego-decode <username> --start {args.start} --end {end_date.strftime('%Y-%m-%d')} --decode"
        if args.all_days:
            decoder_cmd += " --all-days"
        logger.info(f"  {decoder_cmd}")

        return 0

    except (EncodingError, GitCommandError) as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        # Cleanup temp repo if created
        if not args.repo and not args.push and not args.dry_run:
            response = input("\nDelete temporary repository? [y/N]: ")
            if response.lower() == 'y':
                try:
                    encoder.cleanup()
                except OSError:
                    pass
            else:
                logger.info(f"Temporary repository kept at: {encoder.repo_path}")


if __name__ == "__main__":
    exit(main())
