# Contributing to KernelSight AI

Thank you for your interest in contributing to KernelSight AI!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone <your-fork-url>`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Set up the development environment (see [Development Setup](docs/development/setup.md))

## Development Workflow

### Code Style

- **Python**: Follow PEP 8, use `black` for formatting, `mypy` for type checking
- **C/C++**: Follow kernel coding style, use `clang-format`
- **Commit messages**: Use conventional commits format

### Testing

- Write tests for all new features
- Ensure all tests pass before submitting PR
- Run: `pytest tests/`

### Pull Request Process

1. Update documentation for any new features
2. Add tests for new functionality
3. Ensure CI/CD pipeline passes
4. Request review from maintainers
5. Address review feedback

## Architecture Guidelines

- Follow the layered architecture (see [Architecture Overview](docs/architecture/overview.md))
- Keep telemetry collection layer minimal and efficient
- Document performance implications of changes
- Consider deployment to Google AI Studio for agent components

## Code Review Criteria

- Correctness and performance
- Test coverage
- Documentation quality
- Code clarity and maintainability

## Questions?

Open an issue or start a discussion!
