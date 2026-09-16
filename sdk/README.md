# Dark Tower SDK (v0.3)

This folder contains the active prototype toolchain and starter runtime layout.

## Layout

- `toolchain/` — CLI, parser, interpreter, and tests
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
- interpreted subset with functions, lists, control flow, and builtins
- project loading from `DarkTower.toml` and `src/main.dt`
- automated coverage in `sdk/toolchain/tests/test_dt.py`
