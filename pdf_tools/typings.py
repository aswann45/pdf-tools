"""Application-specific types."""

from enum import StrEnum


class Align(StrEnum):
    """CLI selection helper for horizontal/vertical alignment."""

    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
