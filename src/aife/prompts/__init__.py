"""Prompt templates used by the measurement pipeline."""

from __future__ import annotations

from functools import cache
from importlib.resources import files


@cache
def load(name: str) -> str:
    return files(__package__).joinpath(f"{name}.txt").read_text(encoding="utf-8")
