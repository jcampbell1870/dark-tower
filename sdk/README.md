# Dark Tower SDK (v0.2)

This folder contains starter materials for the Dark Tower toolchain and runtime layout.

## Layout

- `toolchain/` — compiler and CLI placeholders
- `runtime/` — runtime component placeholders
- `templates/` — starter app templates

## Prototype Commands

- `dt --help`
- `dt run <path>`
- `dt build <path> -o <output>`

## Current State

Runnable CLI foundation:

- `dt` launcher at repository root
- implementation in `sdk/toolchain/dt.py`
- supports simple `print("...");` execution and build artifact generation
