# Dark Tower SDK (v0.4)

This folder contains the active prototype toolchain and starter runtime layout.

## Layout

- `toolchain/` — CLI, parser, bytecode compiler, VM, and tests
- `runtime/` — future runtime expansion area
- `templates/` — starter app templates

## Available Commands

- `dt --help`
- `dt init <name>`
- `dt run [path]`
- `dt build [path] -o <output> [--target <triple>]`
- `dt test [path]`

## Current State

Runnable CLI foundation:

- `dt` launcher at repository root
- implementation in `sdk/toolchain/dt.py`
- bytecode-compiled subset with functions, lists, control flow, and builtins
- JSON build artifacts that include compiled bytecode instructions
- project loading from `DarkTower.toml` and `src/main.dt`
- automated coverage in `sdk/toolchain/tests/test_dt.py`
