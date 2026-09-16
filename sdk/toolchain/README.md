# Dark Tower CLI Toolchain

Prototype implementation:

- `dt.py` provides `dt init`, `dt run`, `dt build`, and `dt test`
- `dt run` lexes, parses, compiles to bytecode, and executes the result on the VM
- `dt build` emits a JSON artifact describing project metadata, sources, discovered functions, and compiled bytecode
- `dt test` runs `@test`-annotated functions with `assert_eq`
- `tests/test_dt.py` verifies CLI help, project loading, language execution, scaffolding, and the crypto chess sample
