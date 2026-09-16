# Dark Tower Language (DTL) Specification v0.1

## 1. Design Goals

DTL is designed to combine:

- Systems-level control (memory awareness, predictable performance)
- Application productivity (safe defaults, modern module tooling)
- Cross-target compilation (desktop, mobile, console, server)

## 2. Core Philosophy

1. **Safe by default, explicit when unsafe**.
2. **Readable syntax with strict semantics**.
3. **Deterministic builds and reproducible binaries**.
4. **First-class concurrency and async I/O**.

## 3. File and Package Structure

- Source extension: `.dt`
- Package manifest: `DarkTower.toml`
- Entry module convention: `src/main.dt`

Example package:

```text
my-app/
  DarkTower.toml
  src/
    main.dt
    net/
      client.dt
```

## 4. Lexical Syntax

- UTF-8 source files
- Significant tokens: identifiers, literals, operators, delimiters
- Comments:
  - `//` single-line
  - `/* ... */` block

Identifiers:
- Start with letter or `_`
- Continue with letters, digits, `_`

## 5. Types

Primitive types:
- `i8 i16 i32 i64`
- `u8 u16 u32 u64`
- `f32 f64`
- `bool`
- `char`
- `str` (UTF-8 string slice)

Compound types:
- Arrays: `[T; N]`
- Slices: `[T]`
- Tuples: `(T1, T2, ...)`
- Structs
- Enums
- Interfaces

Ownership model (v0.1):
- Move semantics by default for heap-backed types
- Copy semantics for explicit `copy` types
- Borrowing with `&T` and `&mut T`

## 6. Variables and Constants

```dt
let x: i32 = 42;
let mut count: i32 = 0;
const MAX_USERS: u32 = 1000;
```

## 7. Functions

```dt
fn add(a: i32, b: i32) -> i32 {
  return a + b;
}
```

- Parameters are immutable by default.
- Explicit `mut` for mutable bindings.

## 8. Control Flow

- `if / else`
- `match`
- `while`
- `for`
- `loop`

```dt
match status {
  Status::Ok => log("ok"),
  Status::Err(code) => log_err(code),
}
```

## 9. Error Handling

Result and option types:
- `Result<T, E>`
- `Option<T>`

Error propagation operator: `?`

```dt
fn load_user(id: u64) -> Result<User, IoError> {
  let raw = fs::read_text(user_path(id))?;
  return parse_user(raw)?;
}
```

## 10. Modules and Visibility

- `mod` to declare modules
- `pub` to expose symbols
- `use` to import symbols

## 11. Concurrency Model

- Structured tasks
- Channels for message passing
- Actor-style runtime optional profile

```dt
task worker = spawn fn() {
  process_queue();
};
await worker;
```

## 12. FFI

- Explicit boundary with `extern`
- Stable C ABI in v0.1

## 13. Build Targets

- `dtos-desktop-x64`
- `dtos-mobile-arm64`
- `dtos-console-a64`
- `linux-x64` (bootstrap target)

## 14. Tooling Commands (planned)

- `dt init`
- `dt build`
- `dt run`
- `dt test`
- `dt fmt`
- `dt doc`

## 15. Security Rules

- Unsafe blocks must be explicitly marked `unsafe { ... }`
- Capability checks required for filesystem/network APIs on DTOS

## 16. Standard Library Surface (initial)

- `core` (no allocator)
- `std` (allocator + I/O)
- `dtos` (platform APIs)
