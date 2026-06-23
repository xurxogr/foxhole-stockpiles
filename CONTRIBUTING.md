# Contributing to Foxhole Stockpiles

Thank you for your interest in contributing to Foxhole Stockpiles! This document provides guidelines for contributing to the project.

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

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/your-username/foxhole-stockpiles.git
   cd foxhole-stockpiles
   ```

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

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, etc.)
- Keep the first line under 72 characters
- Reference issue numbers when applicable

Examples:
```
Add support for custom resolution templates
Fix OCR detection for low-contrast screenshots
Add a new output handler format
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

## License

By contributing to Foxhole Stockpiles, you agree that your contributions will be licensed under the MIT License.
