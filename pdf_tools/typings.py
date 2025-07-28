"""Application-specific types."""

from enum import Enum


class Align(str, Enum):
    """CLI selection helper for horizontal/vertial alignment."""

    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
