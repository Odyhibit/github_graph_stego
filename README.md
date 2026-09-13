# GitHub Contribution Graph Steganography

A steganographic system that encodes secret messages into GitHub contribution patterns (the green squares on a user's GitHub profile) and decodes them back.

## Overview

This tool uses the temporal nature of git commits and GitHub's visual contribution graph as a covert data transmission channel. Messages are encoded as patterns of commits on specific dates, where each day's commit count corresponds to a portion of the binary-encoded message.

## How It Works

### Encoding Process

1. **Text to Binary**: Converts each character to 8-bit binary representation
2. **Binary Chunking**: Splits binary into 2-bit segments (4 possible values: 00, 01, 10, 11)
3. **Marker Framing**: Adds a darkest-green day at the start and end of the payload
4. **Commit Mapping**: Maps each 2-bit value to a contribution graph state:
   - `00` → 0 commits (empty/gray)
   - `01` → 1 commit (light green)
   - `10` → 5 commits (medium-light green)
   - `11` → 10 commits (medium-dark green)
   - start/end marker → 20 commits (darkest green)
5. **Backdated Commits**: Creates git commits with manipulated timestamps
6. **GitHub Push**: Pushes to GitHub where the contribution graph visually encodes the message

### Decoding Process

1. **Public Fetch**: Retrieves contribution counts from GitHub's public contribution graph
2. **Marker Detection**: Finds the darkest-green start and end marker days
3. **Reverse Mapping**: Converts the cells between markers back to 2-bit patterns
4. **Binary Reassembly**: Combines 2-bit chunks into 8-bit bytes
5. **Binary to ASCII**: Converts bytes back to readable text

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd github_graph_stego

# Create an isolated environment
python -m venv .venv
source .venv/bin/activate

# Install package and CLI commands
pip install -e .
```

## Detection Tools

In addition to the steganography tools, this project includes **detection tools** for identifying GitHub stat padding and steganographic activity:

- **graph-stego-scrape** - Scrapes public contribution data without API authentication
- **graph-stego-detect-backdating** - Analyzes repositories for backdated commits

See [DETECTION.md](docs/DETECTION.md) for detailed usage and interpretation guide.

```bash
# Detect suspicious contribution patterns (no token required)
graph-stego-scrape username --year 2024 --analyze

# Detect backdated commits in a repository
graph-stego-detect-backdating https://github.com/username/repo --show-suspicious
```

## Usage

### Encoding a Message

```bash
# Basic encoding with temporary repository
graph-stego-encode "Secret Message" --start 2024-01-01

# Encode into existing repository and push to GitHub
graph-stego-encode "CTF{flag}" --start 2024-01-01 \
  --repo ./my-repo \
  --remote git@github.com:username/repo.git \
  --push

# Use all days (including weekends)
graph-stego-encode "Message" --start 2024-01-01 --all-days

# Custom git author
graph-stego-encode "Message" --start 2024-01-01 \
  --author "John Doe" \
  --email "john@example.com"
```

### Decoding a Message

```bash
# Analyze a date range (shows capacity and statistics)
graph-stego-decode username --start 2024-01-01 --end 2024-01-31

# Decode message from contribution graph
graph-stego-decode username \
  --start 2024-01-01 \
  --end 2024-02-28 \
  --decode

# Optionally use GitHub GraphQL API with a token
graph-stego-decode username \
  --token ghp_xxxxxxxxxxxxx \
  --start 2024-01-01 \
  --end 2024-02-28 \
  --decode
```

## Encoding Capacity

With weekday-only encoding (Mon-Fri):
- Each day encodes 2 bits (1/4 byte)
- The start and end markers use 2 additional days
- Approximately **5-6 characters per month**
- A 10-character message requires ~40 weekdays (~2 months)

## GitHub API Token

Decoding works without a token by scraping GitHub's public contribution graph. You can optionally provide a GitHub personal access token to use the GraphQL API instead:

1. Create a token at: https://github.com/settings/tokens
2. No special scopes required (public data access only)
3. Pass it with `--token` or set `GITHUB_TOKEN`

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
graph-stego-decode username --start 2024-01-01 --end 2024-02-28 --decode
```

## Configuration File (Optional)

Create a `config.json` file for default settings:

```json
{
  "author_name": "John Doe",
  "author_email": "john@example.com",
  "commit_message_template": "Update",
  "weekdays_only": true
}
```

## Security Considerations

### Legal and Ethical Use

- **Authorized Use Only**: This tool is for educational purposes, CTF challenges.
- **Respect Terms of Service**: Ensure compliance with GitHub's Terms of Service
- **Academic/Research**: Suitable for demonstrating steganographic techniques in educational settings

### Detection Risks

This steganographic method has several detectable characteristics:

1. **Pattern Recognition**: Commit counts of exactly 1, 5, or 10 with rare 20+ commit markers are statistically unusual
2. **Timing Analysis**: All commits at the same time (12:00 by default) is suspicious
3. **Statistical Analysis**: Unusual uniformity in contribution patterns
4. **Metadata Forensics**: Backdated commits are visible in raw git data

### Not Suitable For

- High-security applications requiring undetectable communication
- Circumventing organizational security policies
- Any malicious or unauthorized activities

### Limitations

- **Low Capacity**: ~5 characters per month (weekdays only)
- **Requires GitHub Access**: Must be able to push to a repository
- **Date Range Dependency**: Decoder needs a date range containing the start/end markers
- **Public Visibility**: Contribution graphs are publicly visible

## Technical Details

### Dependencies

- Python 3.7+
- `requests` library for GitHub API
- `beautifulsoup4` for contribution scraping
- Git installed and accessible via command line

### File Structure

```
github_graph_stego/
├── github_graph_stego/ # Core package
│   ├── encoding.py     # Message encoding and git writing
│   ├── decoding.py     # Message extraction
│   ├── github.py       # Public contribution scraping
│   └── detection.py    # Backdating/stat-padding detection
├── pyproject.toml      # Package metadata and console scripts
├── tests/              # Unit and integration tests
├── docs/               # Format, detection, and project notes
└── README.md           # This file
```

### Environment Variables

The encoder manipulates these git environment variables:
- `GIT_AUTHOR_DATE`: Sets the author date for commits
- `GIT_COMMITTER_DATE`: Sets the committer date for commits
- `GIT_COMMITTER_NAME`: Sets the committer name
- `GIT_COMMITTER_EMAIL`: Sets the committer email

## Example Workflow

```bash
# 1. Encode a message
graph-stego-encode "Hello World" --start 2024-01-01 --repo ./stego-repo

# 2. Push to GitHub
cd stego-repo
git remote add origin git@github.com:username/stego-repo.git
git push -f origin main

# 3. Wait a few minutes for GitHub to update the contribution graph

# 4. Decode the message
graph-stego-decode username --start 2024-01-01 --end 2024-03-01 --decode
# Output: Hello World
```

## Troubleshooting

### Encoding Issues

**Problem**: "Push failed"
- Ensure the GitHub repository exists
- Verify SSH keys or authentication tokens are configured
- Check that you have write access to the repository

**Problem**: "git command not found"
- Install git: https://git-scm.com/downloads
- Ensure git is in your system PATH

### Decoding Issues

**Problem**: "Rate limit exceeded"
- Retry later or use a GitHub personal access token with `--token`
- Wait an hour for rate limits to reset

**Problem**: "Failed to decode message"
- Verify the correct date range (must match encoding period)
- Ensure `--all-days` flag matches the encoding settings
- Check that commits were successfully pushed to GitHub

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project is for educational and research purposes. Use responsibly and ethically.

## Acknowledgments

Inspired by various steganographic techniques and the creative use of metadata for covert communication.

## References

- [Steganography on Wikipedia](https://en.wikipedia.org/wiki/Steganography)
- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [Git Internals - Environment Variables](https://git-scm.com/book/en/v2/Git-Internals-Environment-Variables)
