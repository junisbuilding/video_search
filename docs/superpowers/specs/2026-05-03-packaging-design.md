# Packaging Design

**Goal:** Make `git clone → running server` a three-command experience for a macOS developer.

**Target:** macOS, developer/technical user, git clone (not PyPI).

**Non-goals:** Docker, Homebrew formula, PyPI release, Windows/Linux support, non-technical installer.

---

## What changes

### 1. Commit `uv.lock`

`uv.lock` is currently untracked. Committing it ensures reproducible dependency resolution across machines and time. Standard practice for applications (as opposed to libraries).

### 2. Makefile

Six self-documenting targets. Running bare `make` prints help rather than accidentally starting the server.

```makefile
.DEFAULT_GOAL := help

setup:  ## Install dependencies (run once after clone)
	CMAKE_ARGS="-DLLAMA_METAL=on" uv sync --all-extras

run:    ## Start the server (http://localhost:8083)
	uv run videosearch serve

test:   ## Run the test suite
	uv run pytest

lint:   ## Ruff check + format check
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

fmt:    ## Auto-fix formatting
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

help:   ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'
```

**`CMAKE_ARGS="-DLLAMA_METAL=on"`** — `llama-cpp-python` builds without this flag succeed but run CPU-only on Apple Silicon. Setting it at `make setup` time enables Metal GPU inference without requiring the developer to know the flag exists.

### 3. README

Replace the current stub with a real quick-start. No architecture docs or API reference (those belong in `docs/`).

```markdown
# video-search

Semantic search over local videos — find moments by describing what's happening.

## Quick start

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Xcode CLI tools (`xcode-select --install`)

git clone <repo>
cd video-search
make setup    # first time only — installs deps with Metal GPU support
make run      # starts server at http://localhost:8083

On first launch a setup modal guides you through downloading the required models (~4 GB).

## Configuration

Data and models default to `~/Library/Application Support/videosearch/`.

| Override | Flag | Env var |
|---|---|---|
| Data directory | `--data-dir PATH` | `VS_DATA_DIR` |
| Models directory | `--models-dir PATH` | `VS_MODELS_DIR` |
| Port | `--port N` | `VS_PORT` |

A `config.toml` can be passed via `--config PATH`. Keys match env var names without the `VS_` prefix (e.g. `port = 8084`).

## Development

make test   # run test suite
make lint   # ruff check + format check
make fmt    # auto-fix formatting
```

---

## Files changed

| File | Action |
|---|---|
| `uv.lock` | Add to git (was untracked) |
| `Makefile` | Create |
| `README.md` | Replace |
