"""Backward-compatible entry point for the backend application."""

from backend.app import *  # noqa: F403
from backend.app import main

if __name__ == "__main__":
    main()
