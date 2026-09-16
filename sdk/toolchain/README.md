# Dark Tower CLI Toolchain

Prototype implementation:

- `dt.py` provides `dt init`, `dt run`, `dt build`, and `dt test`
- `dt run` executes a parsed DTL subset instead of the old print-only extractor
- `dt build` emits a JSON artifact describing project metadata, sources, and discovered functions
- `dt test` runs `@test`-annotated functions with `assert_eq`
- `tests/test_dt.py` verifies CLI help, project loading, language execution, scaffolding, and the crypto chess sample
