# Getting Started with Workspace OS

**5-minute quickstart guide**

Workspace OS is a local-first operating system for AI-assisted work. This guide will get you up and running in under 5 minutes.

## Prerequisites

- Python 3.11 or higher
- Git
- A terminal (bash, zsh, or PowerShell)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/workspace-os.git
cd workspace-os
```

### 2. Install the Package

```bash
pip install -e .
```

This installs the `workspace` command globally.

### 3. Verify Installation

```bash
workspace --help
```

You should see the Workspace OS command-line interface help output.

## Initialize Your Workspace

### 1. Create Your Configuration

Copy the example configuration and customize it for your environment:

```bash
cp config/workspace.sources.example.json config/workspace.sources.local.json
```

### 2. Edit Configuration

Open `config/workspace.sources.local.json` in your editor. Update the paths to match your local repository structure:

```json
{
  "sources": [
    {
      "name": "adev",
      "type": "doctrine",
      "responsibility": "Operating doctrine, validation standards, and delivery guardrails.",
      "path": "/absolute/path/to/your/adev",
      "search": true
    },
    {
      "name": "scanales-kb",
      "type": "evidence",
      "responsibility": "Sanitized evidence, implementation notes, decisions, and verified lessons.",
      "path": "/absolute/path/to/your/knowledge-base",
      "search": true
    },
    {
      "name": "workspace-os",
      "type": "product",
      "responsibility": "Product roadmap, architecture, and workspace controller implementation.",
      "path": ".",
      "search": true
    }
  ]
}
```

**Note:** If you don't have the other repositories yet, you can start with just `workspace-os` configured.

## Your First Cycle

### 1. Check Workspace Status

See the health of all configured repositories:

```bash
workspace --config config/workspace.sources.local.json status
```

**Example output:**
```
workspace-os     product    clean    branch=main changes=0 untracked=0
adev             doctrine   clean    branch=main changes=0 untracked=0
scanales-kb      evidence   clean    branch=main changes=2 untracked=1
```

### 2. Search Your Workspace

Find content across all configured sources:

```bash
workspace --config config/workspace.sources.local.json search "agent alignment"
```

**Example output:**
```
adev:docs/principles/agents.md:12: Agents must validate scripts before release.
scanales-kb:sessions/2024-06-15.md:45: Agent successfully aligned with ADEV principles.
```

### 3. Build Context for a Task

Generate a governed context pack for agent work:

```bash
workspace --config config/workspace.sources.local.json context "setting up CI/CD"
```

**Example output:**
```markdown
# Context Pack: setting up CI/CD

## Relevant Knowledge

### From doctrine (adev)
- CI/CD pipelines must include security scanning
- Deployment requires explicit approval gates
- Test coverage must exceed 80% before merge

### From evidence (scanales-kb)
- GitHub Actions preferred for CI/CD automation
- Pre-commit hooks reduce pipeline failures

The context pack also includes semantically similar memory entries from prior work when the local memory store has relevant summaries, so older but related iterations can still influence the starting prompt.
```

### 4. Classify Content

Determine where new content belongs in your workspace model:

```bash
workspace --config config/workspace.sources.local.json classify "Agents must validate scripts before release."
```

**Example output:**
```
target=adev
confidence=high
reason=This is a reusable operating rule that applies across projects.
```

### 5. Validate Your Workspace

Run validation checks across all sources:

```bash
workspace --config config/workspace.sources.local.json validate
```

**Example output:**
```
PASS Configuration loaded: 3 sources registered
PASS Source registry valid: all required fields present
PASS Source health: all sources reachable
PASS Housekeeping: no temporary artifacts found
```

## Understanding the Output

### Status Output

The `status` command shows:

- **name**: Repository identifier
- **type**: Source type (doctrine, evidence, execution, product)
- **state**: Repository state (clean, dirty, missing, not-git, error)
- **branch**: Current branch
- **changes**: Number of modified files
- **untracked**: Number of untracked files
- **ahead/behind**: Divergence from remote (if applicable)

### Search Output

Search results show matches in the format:
```
source:path:line_number: content
```

This makes it easy to locate and review found content.

### Classification Output

The `classify` command helps you understand:

- **target**: Which repository should own the content (adev, scanales-kb, homedir, google)
- **confidence**: How certain the classification is (high, medium, low)
- **reason**: Why this classification was chosen

## Next Steps

### Capture Your First Session

Record a sanitized session note:

```bash
workspace --config config/workspace.sources.local.json capture \
  --type session \
  --title "First workspace setup" \
  --text "Configured workspace sources and verified basic commands." \
  --write
```

### Promote a Rule to Doctrine

Convert learned lessons into reusable doctrine:

```bash
workspace --config config/workspace.sources.local.json promote \
  --to adev \
  --rule "Configuration files should use absolute paths for cross-platform compatibility." \
  --evidence "scanales-kb:sessions/2024-06-15.md"
```

### Run Housekeeping

Find temporary artifacts that should be cleaned up:

```bash
workspace --config config/workspace.sources.local.json housekeeping
```

### Explore the Web Interface

Launch the local web pilot:

```bash
workspace --config config/workspace.sources.local.json web
```

Then open http://127.0.0.1:8765 in your browser.

### Try Advanced Workflows

Once comfortable with the basics, explore:

- **Cycle Management**: `workspace cycle --help`
- **Memory Store**: `workspace memory --help`
- **Batch Tracking**: `workspace batch --help`
- **Shell Mode**: `workspace shell` (runs the onboarding tutorial on first use; add `--skip-onboarding` to bypass it)
- **Onboarding**: `workspace onboarding`

## Common Patterns

### Daily Workflow

1. Check status: `workspace status`
2. Search for related work: `workspace search "topic"`
3. Build context: `workspace context "task description"`
4. Do your work
5. Capture learnings: `workspace capture --type session ...`
6. Validate before commit: `workspace validate`

### Agent Delegation

1. Build context pack: `workspace context "task"`
2. Share context with your AI assistant
3. Review agent output
4. Capture session notes
5. Promote reusable patterns to doctrine

### Before Deliverables

1. Run validation: `workspace validate`
2. Check housekeeping: `workspace housekeeping`
3. Search for similar work: `workspace search "topic"`
4. Classify new content: `workspace classify --path new-file.md`

## Troubleshooting

### Command Not Found

If `workspace` is not found after installation:

```bash
# Reinstall in development mode
pip install -e .

# Or use the module form
python -m workspace_os --help
```

### Configuration Errors

If you see "error: Configuration file not found":

```bash
# Use explicit config path
workspace --config config/workspace.sources.local.json status

# Or set an environment variable
export WORKSPACE_CONFIG=config/workspace.sources.local.json
workspace status
```

### Missing Sources

If a source shows as "missing":

- Verify the path in your configuration is absolute and correct
- Ensure the repository exists at that location
- Initialize missing repositories if needed

### Path Issues on Windows

Use forward slashes or escaped backslashes in JSON configuration:

```json
"path": "C:/Users/username/repos/adev"
```

or

```json
"path": "C:\\Users\\username\\repos\\adev"
```

## Quick Reference

### Most Used Commands

```bash
# Check all repository status
workspace status

# Search across all sources
workspace search "query"

# Build task context
workspace context "topic"

# Classify content
workspace classify "text"

# Validate workspace
workspace validate

# Capture a session
workspace capture --type session --title "Title" --text "Content" --write

# Run housekeeping
workspace housekeeping
```

### Shortening Commands

Create an alias for convenience:

```bash
# In .bashrc or .zshrc
alias wos='workspace --config config/workspace.sources.local.json'

# Then use:
wos status
wos search "query"
```

## Learn More

- [Product Vision](docs/product/vision.md) - Understand the goals and outcomes
- [Roadmap](docs/product/roadmap.md) - See what's implemented and what's coming
- [Architecture](docs/architecture/overview.md) - Learn the system design
- [Operating Model](docs/product/operating-model.md) - Understand responsibility boundaries

## Getting Help

- Check `workspace <command> --help` for detailed command usage
- Review the `docs/` directory for comprehensive documentation
- Open an issue for bugs or feature requests

---

You're now ready to use Workspace OS to coordinate your AI-assisted work across repositories, knowledge bases, and deliverables.
