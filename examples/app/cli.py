"""Command-line interface — a Fire launcher (entry point: app.cli:run)."""

import asyncio

import fire

from app import main


class CLI:
    """My Project command-line interface."""

    def serve(self) -> None:
        """Start the application."""
        asyncio.run(main.serve())


def run() -> None:
    """Entry point: dispatch subcommands through Fire."""
    fire.Fire(CLI)


if __name__ == "__main__":
    run()
