from typing import Protocol


class OCRClient(Protocol):
    """Interface for optical character recognition clients."""

    def read_text(self, image) -> list[str]:
        """Extract text candidates from an image."""
        ...
