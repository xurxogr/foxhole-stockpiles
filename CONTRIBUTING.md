# Contributing to Foxhole Stockpiles

Thank you for your interest in contributing to Foxhole Stockpiles! This document provides guidelines for contributing to the project.

> For *running* the tool — installing from source on macOS/Linux, the
> command-line interface, building custom OCR databases, and configuration — see
> [docs/advanced.md](docs/advanced.md).

## Ways to Contribute

- **Report Bugs**: Open an issue describing the problem, steps to reproduce, and your environment
- **Suggest Features**: Open an issue describing the feature and its use case
- **Submit Pull Requests**: Fix bugs, add features, or improve documentation
- **Improve Documentation**: Help make the docs clearer and more comprehensive

## Reporting Bugs

When reporting bugs, please include:

1. **Environment Information**:
   - Python version (`python --version`)
   - Operating system
   - Installation method (pip, source, etc.)
   - Relevant package versions

2. **Steps to Reproduce**:
   - Exact commands or code that trigger the issue
   - Input files (if applicable and not sensitive)
   - Expected vs actual behavior

3. **Error Output**:
   - Full error messages and stack traces
   - Log output (use `--log-level debug` for verbose logs)

## Submitting Pull Requests

### Development Setup

1. **Fork the repository on GitHub, then clone your fork** (replace `<your-username>` with your own GitHub username):
   ```bash
   git clone https://github.com/<your-username>/foxhole-stockpiles.git
   cd foxhole-stockpiles
   ```
   > Just want to run the tool, not contribute changes? Clone the original repo
   > directly instead — see [docs/advanced.md](docs/advanced.md#install-and-run-from-source).

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -e .[dev]
   ```

4. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

### Code Quality Standards

This project follows strict code quality guidelines:

- **Linting**: Code must pass `ruff check`
- **Type Checking**: Code must pass `mypy` type checks
- **Formatting**: Code is formatted with `ruff format`
- **Docstrings**: Use Google-style docstrings for all public functions/classes
- **Testing**: Add tests for new features and bug fixes

### Running Quality Checks

```bash
# Run linter (all packages)
ruff check .

# Run formatter check
ruff format --check .

# Run type checker (strict mode, all packages)
mypy foxhole_stockpiles fs_tools

# Run all pre-commit hooks
pre-commit run --all-files

# Run tests
pytest

# Run tests with coverage
pytest --cov=foxhole_stockpiles --cov-report=html
```

### Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Ensure all checks pass**:
   ```bash
   ruff check .
   mypy foxhole_stockpiles fs_tools
   pytest
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request**:
   - Provide a clear description of the changes
   - Reference any related issues
   - Ensure CI checks pass

### Commit Message Guidelines

This project follows [Conventional Commits](https://www.conventionalcommits.org/):
a `<type>(<optional scope>): <description>` first line.

- **type** (lowercase) — one of: `feat`, `fix`, `refactor`, `perf`, `docs`,
  `test`, `chore`, `ci`, or `delete` (used here for removals).
- **scope** (optional) — the area touched, e.g. `feat(output):`, `chore(deps):`.
- Keep the first line under 72 characters.
- Reference issue numbers when applicable, e.g. `(#28)`.

Examples (from this repo's history):
```
feat: Add clipboard stockpile scanning
fix: use hex code instead of display name in the clipboard parsing
feat(output): add Google Sheets export destination (#28)
refactor: drop OpenCV and delegate all OCR/matching to fs-ocr
chore(deps): bump actions/checkout from 6 to 7
```

## Code Style Guidelines

- **Type Hints**: All functions must have type hints
- **Pydantic Models**: Use Pydantic for data validation and settings
- **Error Handling**: Raise specific exceptions with clear error messages
- **Logging**: Use structured logging (see `foxhole_stockpiles/core/logging.py`)
- **Async/Await**: Use `async`/`await` for I/O operations in API code
- **Code Style**: Follow existing patterns in the codebase

## Testing Guidelines

- **Test Coverage**: Aim for high test coverage (currently >80%)
- **Test Organization**: Use test classes to group related tests
- **Fixtures**: Use pytest fixtures for common test setup
- **Async Tests**: Mark async tests with `@pytest.mark.asyncio`
- **Mocking**: Use `unittest.mock` or `pytest-mock` for external dependencies

Example test structure:
```python
import pytest

class TestStockpileScanner:
    """Test suite for stockpile scanner functionality."""

    def test_detect_items_success(self, scanner, sample_image):
        """Test successful item detection from screenshot."""
        result = scanner.scan(sample_image)
        assert len(result.items) > 0
        assert all(item.confidence > 0.85 for item in result.items)

    def test_detect_items_invalid_image(self, scanner):
        """Test scanner handles invalid image gracefully."""
        with pytest.raises(ValueError, match="Invalid image"):
            scanner.scan(None)
```

## Documentation Guidelines

- Update README.md for user-facing changes
- Update relevant documentation in `docs/` for architectural changes
- Add docstrings to all public functions and classes
- Include examples in docstrings when helpful

## Building the Windows Executable

```bash
pip install pyinstaller
python build_fs.py
```

This produces `fs.exe` and `fs-tools.exe` in `dist/` (~50–80 MB each), bundling
all Python dependencies. External tools (`repak.exe`, `umodel.exe`) are still
provided separately. The CI/release workflow runs this automatically on
`vX.Y.Z` tags and publishes the executables as GitHub Release assets.

## Translations

Translation files live in `foxhole_stockpiles/i18n/translations/`, one JSON per
language (e.g. `en.json`, `es.json`). To add or improve a language:

1. Copy `en.json` as a template.
2. Translate the string values (keep the keys unchanged).
3. Update `language_name` and `language_code` at the top of the file.
4. Open a pull request.

(End users can override translations next to the packaged executable without
rebuilding — see [Languages](README.md#languages) in the main README.)

## License

By contributing to Foxhole Stockpiles, you agree that your contributions will be licensed under the MIT License.
