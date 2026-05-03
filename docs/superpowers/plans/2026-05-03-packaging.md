# Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `git clone → running server` a three-command experience (`make setup`, `make run`) for a macOS developer.

**Architecture:** Three file changes only — commit the lockfile for reproducible installs, add a self-documenting Makefile, and rewrite the README with a real quick-start. No code changes.

**Tech Stack:** GNU Make (ships with Xcode CLI tools), uv, ruff.

---

## File map

- Modify: `uv.lock` — add to git (currently untracked)
- Create: `Makefile` — six targets: `help` (default), `setup`, `run`, `test`, `lint`, `fmt`
- Modify: `README.md` — replace stub with quick-start, config table, dev commands

---

### Task 1: Commit uv.lock

**Files:**
- Modify: `uv.lock` (stage and commit — file already exists, just untracked)

- [ ] **Step 1: Verify the file exists and is untracked**

```bash
git status uv.lock
```

Expected output:
```
?? uv.lock
```

- [ ] **Step 2: Stage and commit**

```bash
git add uv.lock
git commit -m "chore: commit lockfile for reproducible installs"
```

- [ ] **Step 3: Verify it is tracked**

```bash
git status uv.lock
```

Expected: no output (clean).

---

### Task 2: Create Makefile

**Files:**
- Create: `Makefile`

**Important:** Makefile recipes MUST be indented with a real tab character (`\t`), not spaces. If your editor auto-converts tabs to spaces, disable that for this file.

- [ ] **Step 1: Create `Makefile` with this exact content**

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

- [ ] **Step 2: Verify `make help` lists all targets**

```bash
make help
```

Expected output (order may vary):
```
  setup      Install dependencies (run once after clone)
  run        Start the server (http://localhost:8083)
  test       Run the test suite
  lint       Ruff check + format check
  fmt        Auto-fix formatting
  help       List available targets
```

- [ ] **Step 3: Verify `make` with no arguments also prints help**

```bash
make
```

Expected: same output as `make help`.

- [ ] **Step 4: Verify `make lint` passes**

```bash
make lint
```

Expected: exits 0 with no errors. (If ruff reports issues, fix them with `make fmt` before committing.)

- [ ] **Step 5: Verify `make test` passes**

```bash
make test
```

Expected: `181 passed` (or higher if tests have been added).

- [ ] **Step 6: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile with setup, run, test, lint, fmt targets"
```

---

### Task 3: Rewrite README

**Files:**
- Modify: `README.md`

The current README is a 6-line stub. Replace it entirely with the content below.

- [ ] **Step 1: Replace `README.md` with this content**

```markdown
# video-search

Semantic search over local videos — find moments by describing what's happening.

## Quick start

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Xcode CLI tools (`xcode-select --install`)

\`\`\`sh
git clone <repo-url>
cd video-search
make setup    # first time only — installs deps with Metal GPU support
make run      # starts server at http://localhost:8083
\`\`\`

On first launch a setup modal guides you through downloading the required models (~4 GB).

## Configuration

Data and models default to `~/Library/Application Support/videosearch/`.

| Setting | CLI flag | Env var |
|---|---|---|
| Data directory | `--data-dir PATH` | `VS_DATA_DIR` |
| Models directory | `--models-dir PATH` | `VS_MODELS_DIR` |
| Port | `--port N` | `VS_PORT` |

A `config.toml` can be passed via `--config PATH`. Keys match env var names without the `VS_` prefix (e.g. `port = 8084`).

## Development

\`\`\`sh
make test   # run test suite
make lint   # ruff check + format check
make fmt    # auto-fix formatting
\`\`\`
```

- [ ] **Step 2: Verify the file renders correctly**

```bash
cat README.md
```

Check: quick-start block is present, config table has 3 rows, dev section has 3 commands.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with quick-start, config table, dev commands"
```
