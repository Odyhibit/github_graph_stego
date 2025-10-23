#!/usr/bin/env python3
"""
GitHub Contribution Graph Steganography Encoder
Encodes messages into GitHub contribution patterns by creating backdated commits
"""

import os
import subprocess
import argparse
from datetime import datetime, timedelta
import tempfile
import shutil


class GitHubContributionEncoder:
    def __init__(self, repo_path=None):
        """
        Initialize encoder

        Args:
            repo_path: Path to git repository (will create temp repo if None)
        """
        self.repo_path = repo_path
        self.temp_repo = repo_path is None

        # Commit count mapping for different color levels
        # These counts produce distinct colors on GitHub
        self.level_to_commits = {
            0: 1,  # Light green (00)
            1: 5,  # Medium-light green (01)
            2: 10,  # Medium-dark green (10)
            3: 20  # Darkest green (11)
        }

    def message_to_binary(self, message):
        """
        Convert message to binary string

        Args:
            message: String to encode

        Returns:
            Binary string (e.g., "01001000")
        """
        binary = ""
        for char in message:
            # Convert each character to 8-bit binary
            binary += format(ord(char), '08b')
        return binary

    def binary_to_commit_plan(self, binary_string, start_date, weekdays_only=True):
        """
        Convert binary string to a plan of (date, commit_count) tuples

        Args:
            binary_string: String of 0s and 1s
            start_date: Starting date (datetime object)
            weekdays_only: Only use weekdays for encoding

        Returns:
            List of (date_string, commit_count) tuples
        """
        # Split binary into 2-bit chunks
        chunks = [binary_string[i:i + 2] for i in range(0, len(binary_string), 2)]

        commit_plan = []
        current_date = start_date

        for chunk in chunks:
            # Find next valid date (weekday if required)
            while weekdays_only and current_date.weekday() >= 5:  # Skip weekends
                current_date += timedelta(days=1)

            # Convert 2-bit chunk to level (0-3)
            level = int(chunk, 2)
            commit_count = self.level_to_commits[level]

            # Format date as YYYY-MM-DD
            date_str = current_date.strftime('%Y-%m-%d')
            commit_plan.append((date_str, commit_count))

            # Move to next day
            current_date += timedelta(days=1)

        return commit_plan

    def init_repo(self):
        """
        Initialize git repository (create temp if needed)

        Returns:
            Path to repository
        """
        if self.temp_repo:
            # Create temporary directory
            self.repo_path = tempfile.mkdtemp(prefix='github_stego_')
            print(f"Created temporary repository: {self.repo_path}")

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=self.repo_path, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Create initial file
        readme_path = os.path.join(self.repo_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write('# Steganography Repository\n\nThis repository contains encoded data.\n')

        subprocess.run(['git', 'add', 'README.md'], cwd=self.repo_path, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=self.repo_path,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return self.repo_path

    def create_commit(self, date_str, message, author_name="Steganographer",
                      author_email="stego@example.com"):
        """
        Create a single commit with a specific date

        Args:
            date_str: Date string (YYYY-MM-DD)
            message: Commit message
            author_name: Git author name
            author_email: Git author email
        """
        # Set the date with time
        datetime_str = f"{date_str}T12:00:00"

        # Create environment with custom dates
        env = os.environ.copy()
        env['GIT_AUTHOR_DATE'] = datetime_str
        env['GIT_COMMITTER_DATE'] = datetime_str

        # Make a trivial change to the data file
        data_file = os.path.join(self.repo_path, 'data.txt')
        with open(data_file, 'a') as f:
            f.write(f"{datetime_str}\n")

        # Stage and commit
        subprocess.run(['git', 'add', 'data.txt'], cwd=self.repo_path,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Set committer info in environment as well
        env['GIT_COMMITTER_NAME'] = author_name
        env['GIT_COMMITTER_EMAIL'] = author_email

        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', message,
             '--author', f'{author_name} <{author_email}>'],
            cwd=self.repo_path,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def encode_message(self, message, start_date, weekdays_only=True,
                       author_name="Steganographer", author_email="stego@example.com",
                       commit_message="Update"):
        """
        Encode a message into the git repository

        Args:
            message: Message to encode
            start_date: Starting date (YYYY-MM-DD string or datetime object)
            weekdays_only: Only use weekdays
            author_name: Git author name
            author_email: Git author email
            commit_message: Template for commit messages

        Returns:
            Commit plan (list of date, count tuples)
        """
        # Convert start_date if string
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')

        # Convert message to binary
        print(f"Encoding message: {message}")
        binary = self.message_to_binary(message)
        print(f"Binary representation ({len(binary)} bits): {binary[:64]}{'...' if len(binary) > 64 else ''}")

        # Create commit plan
        commit_plan = self.binary_to_commit_plan(binary, start_date, weekdays_only)

        print(f"\nCommit plan: {len(commit_plan)} days")
        print(f"Date range: {commit_plan[0][0]} to {commit_plan[-1][0]}")
        print(f"Total commits to create: {sum(count for _, count in commit_plan)}")

        # Initialize repo if needed
        if not os.path.exists(os.path.join(self.repo_path or '.', '.git')):
            self.init_repo()

        # Create commits
        print("\nCreating commits...")
        for i, (date_str, commit_count) in enumerate(commit_plan):
            for j in range(commit_count):
                msg = f"{commit_message} {i}-{j}"
                self.create_commit(date_str, msg, author_name, author_email)

            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(commit_plan)} days")

        print(f"\n✓ Encoding complete! Created {sum(count for _, count in commit_plan)} commits")
        print(f"✓ Repository: {self.repo_path}")

        return commit_plan

    def add_remote(self, remote_url, remote_name='origin'):
        """
        Add a remote to the repository

        Args:
            remote_url: GitHub repository URL
            remote_name: Name for the remote (default: origin)
        """
        try:
            # Remove existing remote if present
            subprocess.run(['git', 'remote', 'remove', remote_name],
                           cwd=self.repo_path,
                           stderr=subprocess.DEVNULL)
        except:
            pass

        subprocess.run(['git', 'remote', 'add', remote_name, remote_url],
                       cwd=self.repo_path, check=True)
        print(f"\n✓ Added remote '{remote_name}': {remote_url}")

    def push_to_github(self, branch='main', force=True):
        """
        Push commits to GitHub

        Args:
            branch: Branch name to push
            force: Use force push (needed for backdated commits)
        """
        print(f"\nPushing to GitHub (branch: {branch})...")

        # Rename branch if needed
        subprocess.run(['git', 'branch', '-M', branch], cwd=self.repo_path,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Push
        cmd = ['git', 'push', 'origin', branch]
        if force:
            cmd.insert(2, '-f')

        result = subprocess.run(cmd, cwd=self.repo_path)

        if result.returncode == 0:
            print("✓ Successfully pushed to GitHub!")
            print("\nIMPORTANT: It may take a few minutes for GitHub to update the contribution graph.")
        else:
            print("✗ Push failed. Make sure you have:")
            print("  1. Created the repository on GitHub")
            print("  2. Set up authentication (SSH key or token)")
            print("  3. Added the remote with --remote flag")

    def cleanup(self):
        """Clean up temporary repository"""
        if self.temp_repo and self.repo_path and os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)
            print(f"\nCleaned up temporary repository: {self.repo_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Encode messages into GitHub contribution graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encode a message starting Jan 1, 2024 (creates temp repo)
  python encoder.py "CTF{hidden_flag}" --start 2024-01-01

  # Encode into existing repository
  python encoder.py "CTF{hidden_flag}" --start 2024-01-01 --repo ./my-repo

  # Add remote and push to GitHub
  python encoder.py "CTF{hidden_flag}" --start 2024-01-01 \\
    --remote git@github.com:username/repo.git --push

  # Use all days (not just weekdays)
  python encoder.py "Secret Message" --start 2024-01-01 --all-days

  # Custom git author
  python encoder.py "Message" --start 2024-01-01 \\
    --author "John Doe" --email "john@example.com"
        """
    )

    parser.add_argument("message", help="Message to encode")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--repo", help="Path to git repository (creates temp if not specified)")
    parser.add_argument("--remote", help="GitHub repository URL (e.g., git@github.com:user/repo.git)")
    parser.add_argument("--push", action="store_true", help="Push to GitHub after encoding")
    parser.add_argument("--branch", default="main", help="Branch name (default: main)")
    parser.add_argument("--all-days", action="store_true", help="Use all days (not just weekdays)")
    parser.add_argument("--author", default="Steganographer", help="Git author name")
    parser.add_argument("--email", default="stego@example.com", help="Git author email")
    parser.add_argument("--commit-msg", default="Update", help="Commit message template")

    args = parser.parse_args()

    # Create encoder
    encoder = GitHubContributionEncoder(args.repo)

    try:
        # Encode the message
        commit_plan = encoder.encode_message(
            args.message,
            args.start,
            weekdays_only=not args.all_days,
            author_name=args.author,
            author_email=args.email,
            commit_message=args.commit_msg
        )

        # Add remote if specified
        if args.remote:
            encoder.add_remote(args.remote)

        # Push if requested
        if args.push:
            if not args.remote:
                print("\n✗ Cannot push: no remote specified (use --remote)")
            else:
                encoder.push_to_github(args.branch, force=True)
        else:
            print("\nTo push to GitHub:")
            if args.remote:
                print(f"  cd {encoder.repo_path}")
                print(f"  git push -f origin {args.branch}")
            else:
                print("  1. Add remote: git remote add origin <github-url>")
                print(f"  2. Push: git push -f origin {args.branch}")

        # Show decoder command
        print("\nTo decode this message:")
        end_date = datetime.strptime(args.start, '%Y-%m-%d') + timedelta(days=len(commit_plan))
        print(f"  python decoder.py <username> --start {args.start} --end {end_date.strftime('%Y-%m-%d')} --decode")

    finally:
        # Cleanup temp repo if created
        if not args.repo and not args.push:
            response = input("\nDelete temporary repository? [y/N]: ")
            if response.lower() == 'y':
                encoder.cleanup()
            else:
                print(f"Temporary repository kept at: {encoder.repo_path}")


if __name__ == "__main__":
    main()