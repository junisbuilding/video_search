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
