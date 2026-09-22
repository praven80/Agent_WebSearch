"""Descriptor for a demo option."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..config import Settings
from ..types import RunResult


@dataclass(frozen=True)
class Mode:
    """One of the options, with everything the UI needs to present it."""

    key: str
    number: int
    label: str
    tagline: str
    icon: str
    run: Callable[[str, Settings], RunResult]
    # ``(ready, reason)`` -- reason explains what is missing when not ready.
    preflight: Callable[[Settings], tuple[bool, str]]
    # Bullet points explaining what this option does and why it behaves that way.
    explanation: tuple[str, ...] = field(default_factory=tuple)
    # Whether the search tool is offered to the model at all. Lets the UI tell
    # "no retrieval by design" apart from "retrieval was available and the model
    # chose not to use it", which look identical from the citation count alone.
    offers_search: bool = False

    @property
    def title(self) -> str:
        return f"Option {self.number}: {self.label}"
