"""This module contains the Enum for dry run."""

from enum import Enum, auto


class DryRun(Enum):
    """Enum for dry run."""

    NOT = auto()
    YES = auto()
