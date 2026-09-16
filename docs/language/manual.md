# Dark Tower Language Programming Manual (v0.1)

## Who This Manual Is For

This manual is for developers who want to build software with Dark Tower Language (DTL), from beginner to advanced levels.

## 1) Getting Started

Create a new project:

```bash
dt init hello-tower
cd hello-tower
dt run
```

Generated `src/main.dt`:

```dt
fn main() {
  println("Hello, Dark Tower!");
}
```

## Implemented Prototype Subset

The current runtime executes a practical subset of DTL:

- top-level `fn` declarations
- integers, booleans, strings, and lists
- `let`, assignment, `if/else`, `while`, `for`, and `return`
- builtin helpers: `print`, `println`, `len`, `join`, `push`, `pop`, `clone`, `hash`, `to_string`, and `assert_eq`
- project loading through `DarkTower.toml` with `src/main.dt` as the entry module

Features documented later in this manual that go beyond this subset remain part of the broader language design rather than the current runtime implementation.

## 2) Variables, Mutability, and Constants

```dt
let username: str = "Roland";
let mut score: i32 = 0;
const MAX_SCORE: i32 = 9999;

score = score + 10;
```

## 3) Structs and Methods

```dt
struct Player {
  name: str,
  level: u32,
}

impl Player {
  fn level_up(&mut self) {
    self.level = self.level + 1;
  }
}
```

## 4) Enums and Pattern Matching

```dt
enum SaveState {
  Empty,
  Loaded(str),
  Corrupt(i32),
}

fn describe(state: SaveState) -> str {
  match state {
    SaveState::Empty => "No save",
    SaveState::Loaded(name) => name,
    SaveState::Corrupt(_) => "Corrupt save",
  }
}
```

## 5) Error-First APIs

```dt
fn read_config(path: str) -> Result<str, IoError> {
  return fs::read_text(path);
}

fn boot() -> Result<(), IoError> {
  let cfg = read_config("./config.dt")?;
  print(cfg);
  return Ok(());
}
```

## 6) Async and Concurrency

```dt
async fn sync_profile() -> Result<(), NetError> {
  let profile = await net::get("https://example.com/profile")?;
  cache::store(profile)?;
  return Ok(());
}
```

Use channels:

```dt
let (tx, rx) = channel<i32>(64);
spawn fn() {
  tx.send(7);
};
let value = rx.recv();
```

## 7) Modules and Packages

`DarkTower.toml` example:

```toml
[package]
name = "tower-notes"
version = "0.1.0"
edition = "2026"

[dependencies]
crypto = "0.1"
json = "0.3"
```

Importing modules:

```dt
use net::http::Client;
use io::fs;
```

## 8) Testing

```dt
@test
fn adds_two_numbers() {
  assert_eq(add(2, 2), 4);
}
```

Run:

```bash
dt test
dt test ./samples/crypto-chess
```

`dt test` executes functions marked with the `@test` decorator.

## 9) Building for Targets

```bash
dt build -o build/app.dtb --target linux-x64
dt build ./samples/crypto-chess -o build/crypto-chess.dtb --target dtos-console-a64
```

## 10) Best Practices

- Keep unsafe code isolated.
- Favor pure functions in shared modules.
- Use structured logging in system services.
- Document exported APIs with `///` comments.

## 11) Sample Program: CLI Notes

```dt
fn main() -> Result<(), IoError> {
  let args = env::args();
  if args.len() < 2 {
    print("usage: notes <text>\n");
    return Ok(());
  }

  let entry = args[1];
  fs::append_text("notes.txt", entry + "\n")?;
  print("saved\n");
  return Ok(());
}
```

## 12) Learning Path

1. Syntax and types
2. Ownership and borrowing
3. Error handling with `Result`
4. Async/concurrency
5. Systems APIs and capabilities
