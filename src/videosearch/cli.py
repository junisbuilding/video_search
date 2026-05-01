from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from videosearch.config import Settings, load_config

app = typer.Typer(help="Video search server.")


@app.command()
def serve(
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port to listen on (default: 8083)."),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config.toml."),
    data_dir: Optional[Path] = typer.Option(None, "--data-dir", help="Data directory override."),
    models_dir: Optional[Path] = typer.Option(None, "--models-dir", help="Models directory override."),
) -> None:
    """Start the video search server."""
    if data_dir:
        os.environ["VS_DATA_DIR"] = str(data_dir)
    if models_dir:
        os.environ["VS_MODELS_DIR"] = str(models_dir)

    settings = load_config(config)

    if port is not None:
        settings = settings.model_copy(update={"port": port})

    from videosearch.api.app import create_app
    server_app = create_app(settings)

    typer.echo(f"Starting video search on http://127.0.0.1:{settings.port}")
    uvicorn.run(server_app, host="127.0.0.1", port=settings.port)
