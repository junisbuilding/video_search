# video-search

Semantic search over local videos — find moments by describing what's happening.

## Quick start

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Xcode CLI tools (`xcode-select --install`)

```sh
git clone <repo-url>
cd video-search
make setup    # first time only — installs deps with Metal GPU support
make run      # starts server at http://localhost:8083
```

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

```sh
make test   # run test suite
make lint   # ruff check + format check
make fmt    # auto-fix formatting
```
