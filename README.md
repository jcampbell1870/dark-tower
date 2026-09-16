# Dark Tower

Dark Tower is a new computing platform initiative that includes:

- **Dark Tower Language (DTL)**: a modern systems-and-app language
- **Dark Tower OS (DTOS)**: a unified operating system architecture for desktop, laptop, mobile, and console-class devices
- **Dark Tower Browser (DTB)**: a built-in secure web browser platform
- **Dark Tower Console**: a game-system profile and SDK strategy

> This repository now contains the **v0.3 prototype foundation**: language specification, programming manual, architecture documents, SDK starter layout, website, downloadable starter artifacts, and a runnable `dt` CLI with a small interpreted DTL subset.

## Quick Links

- Language spec: [`docs/language/spec.md`](docs/language/spec.md)
- Language manual: [`docs/language/manual.md`](docs/language/manual.md)
- OS architecture: [`docs/os/architecture.md`](docs/os/architecture.md)
- Browser design: [`docs/browser/design.md`](docs/browser/design.md)
- Console platform profile: [`docs/console/profile.md`](docs/console/profile.md)
- SDK overview: [`sdk/README.md`](sdk/README.md)
- Downloadable starter package: [`releases/dark-tower-sdk-v0.1.zip`](releases/dark-tower-sdk-v0.1.zip)
- GitHub Pages site: [`website/index.html`](website/index.html)

## Current DTL Runtime Capabilities

The prototype runtime now supports:

- project manifests via `DarkTower.toml`
- `dt init`, `dt run`, `dt build`, and `dt test`
- top-level `fn` declarations and `main()` entry points
- integers, booleans, strings, lists, indexing, and nested list mutation
- `let`, assignment, `if/else`, `while`, `for`, and `return`
- builtin helpers including `print`, `println`, `len`, `join`, `push`, `pop`, `clone`, `hash`, `to_string`, and `assert_eq`
- multi-file project loading from `src/**/*.dt`

## Sample Applications

- `samples/hello/` — minimal hello-world DTL project
- `samples/crypto-chess/` — a DTL rewrite sample that models a crypto chess opening, board hashing, and reward scoring

Run them with:

```bash
./dt run /home/runner/work/dark-tower/dark-tower/samples/hello
./dt run /home/runner/work/dark-tower/dark-tower/samples/crypto-chess
./dt test /home/runner/work/dark-tower/dark-tower/samples/crypto-chess
```

## Repository Layout

- `docs/` — technical and user-facing manuals
- `sdk/` — starter SDK structure
- `samples/` — example DTL programs
- `releases/` — downloadable artifacts
- `website/` — GitHub Pages site source

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for style, workflow, and roadmap practices.

## License

MIT. See [`LICENSE`](LICENSE).
