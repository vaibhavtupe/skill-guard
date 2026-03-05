# Contributing to skill-guard

Thank you for your interest in contributing! skill-guard is an open source project and we welcome contributions of all kinds.

## Getting Started

```bash
# Clone the repo
git clone https://github.com/vaibhavtupe/skill-guard.git
cd skill-guard

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
ruff format .
```

## Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Ensure linting passes: `ruff check . && ruff format --check .`
7. Open a Pull Request

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include tests for any new functionality
- Update documentation if you're changing behavior
- The PR description should explain what changed and why
- All CI checks must pass before merge

## Issue Templates

Use the GitHub issue templates for:
- **Bug reports** — include the command you ran, the error output, and your environment
- **Feature requests** — describe the problem you're solving and your proposed solution

## Code Style

- Python 3.11+
- Formatted with `ruff format` (line length: 100)
- Linted with `ruff check` 
- Type hints required for all public functions
- Docstrings for all public functions and classes

## Good First Issues

Look for issues labeled `good first issue` — these are well-scoped and a great way to get familiar with the codebase.

## Questions?

Open a [GitHub Discussion](https://github.com/vaibhavtupe/skill-guard/discussions) for questions, ideas, or feedback.
