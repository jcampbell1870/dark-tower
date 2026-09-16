# Contributing to Dark Tower

Thank you for contributing to the Dark Tower platform.

## Development Principles

1. **Clarity first**: every feature should have documentation.
2. **Secure-by-default**: runtime and OS layers must define clear trust boundaries.
3. **Cross-profile consistency**: desktop/laptop/mobile/console share one core where possible.
4. **Deterministic tooling**: build outputs should be reproducible.

## Branching

- `main` is stable documentation + baseline.
- Feature branches: `feature/<topic>`.
- Fix branches: `fix/<topic>`.

## Pull Requests

A good PR includes:
- Problem statement
- Design summary
- Tests or validation notes
- Documentation updates

## Commit Style

Recommended conventional commit style:

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `refactor: ...`
- `build: ...`

## Roadmap Areas

- DTL parser and bytecode VM
- DTOS microkernel prototype
- Capability-based package manager
- Browser shell prototype
- Console SDK simulation tools
