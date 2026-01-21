# Contributing to CRT

Thank you for your interest in contributing to CRT (Contradiction-Preserving Memory)! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Running Tests](#running-tests)
- [Code Style Guidelines](#code-style-guidelines)
- [Submitting Pull Requests](#submitting-pull-requests)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/AI_round2.git
   cd AI_round2
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/blockhead22/AI_round2.git
   ```

## Development Environment Setup

### Prerequisites

- Python 3.10 or higher
- Ollama (for natural language responses)
- Node.js 18+ (for web UI development, optional)

### Setting Up Python Environment

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - **Windows:** `.venv\Scripts\activate`
   - **macOS/Linux:** `source .venv/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install development dependencies:
   ```bash
   pip install black flake8 pytest pytest-cov
   ```

### Setting Up Ollama

1. Install Ollama from [https://ollama.com/download](https://ollama.com/download)
2. Pull the required model:
   ```bash
   ollama pull llama3.2:latest
   ```
3. Start Ollama server:
   ```bash
   ollama serve
   ```

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Tests with Coverage

```bash
pytest tests/ -v --cov=. --cov-report=term --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`

### Run Specific Test Files

```bash
pytest tests/test_crt_rag.py -v
```

### Run the Stress Test

```bash
python tools/crt_stress_test.py \
  --use-api \
  --api-base-url http://127.0.0.1:8123 \
  --thread-id test_run \
  --reset-thread \
  --turns 15 \
  --sleep 0.05
```

## Code Style Guidelines

We follow Python best practices and PEP 8 standards:

### Formatting with Black

Format your code with Black before committing:

```bash
black .
```

Black configuration is automatic with default settings.

### Linting with flake8

Check code quality with flake8:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

### General Guidelines

- **Line Length:** Maximum 127 characters (Black default)
- **Docstrings:** Use descriptive docstrings for all public functions and classes
- **Type Hints:** Add type hints where appropriate for better code clarity
- **Comments:** Write clear comments for complex logic
- **Naming:**
  - Variables and functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_CASE`

## Submitting Pull Requests

### Before Submitting

1. Ensure all tests pass:
   ```bash
   pytest tests/ -v
   ```

2. Format code with Black:
   ```bash
   black .
   ```

3. Check code with flake8:
   ```bash
   flake8 .
   ```

4. Update documentation if needed

5. Add tests for new features or bug fixes

### Pull Request Process

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/my-bug-fix
   ```

2. Make your changes and commit them:
   ```bash
   git add .
   git commit -m "Add feature: description of feature"
   ```

   **Commit Message Format:**
   - Use present tense ("Add feature" not "Added feature")
   - Be descriptive but concise
   - Reference issues when applicable (e.g., "Fix #123: Description")

3. Push to your fork:
   ```bash
   git push origin feature/my-new-feature
   ```

4. Open a Pull Request on GitHub with:
   - Clear title describing the change
   - Detailed description of what changed and why
   - Reference to related issues
   - Screenshots for UI changes

5. Wait for review and address any feedback

### Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Update relevant documentation
- Ensure CI passes before requesting review
- Be responsive to review feedback

## Reporting Issues

### Bug Reports

Use the bug report template and include:

- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

### Feature Requests

When suggesting new features:

- Explain the use case
- Describe the expected behavior
- Consider alternatives
- Be open to discussion

### Security Issues

For security vulnerabilities, please **DO NOT** open a public issue. Instead, contact the maintainers privately.

## Project Structure

Key directories and files:

```
/crt_api.py                    # FastAPI server
/personal_agent/
  ├── crt_rag.py               # Core retrieval + truth coherence
  ├── crt_memory.py            # Memory storage & retrieval
  ├── crt_ledger.py            # Contradiction tracking
  └── research_engine.py       # External knowledge integration
/frontend/                     # React web interface
/tools/                        # Development and testing tools
/tests/                        # Pytest test suite
/docs/                         # Additional documentation
```

## Questions?

If you have questions about contributing:

1. Check existing documentation in the `/docs` directory
2. Review [BETA_STARTER_KIT.md](BETA_STARTER_KIT.md)
3. Open a discussion on GitHub
4. Contact the maintainers

Thank you for contributing to CRT!
