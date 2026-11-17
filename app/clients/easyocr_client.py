"""EasyOCR wrapper used by the plate recognition agent."""

import easyocr
import numpy as np

PLATE_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class EasyOCRClient:
    """EasyOCR implementation of the OCR client interface."""

    def __init__(
        self,
        languages: list[str] | None = None,
        min_confidence: float = 0.25,
        use_gpu: bool = False,
    ) -> None:
        self.languages = languages or ["en"]
        self.min_confidence = min_confidence
        self.reader = easyocr.Reader(self.languages, gpu=use_gpu)

    def read_text(self, image: np.ndarray) -> list[str]:
        """Return text candidates whose OCR confidence passes the threshold."""
        results = self.reader.readtext(
            image,
            detail=1,
            paragraph=False,
            allowlist=PLATE_ALLOWLIST,
        )

        candidates: list[str] = []

        for result in results:
            if len(result) < 3:
                continue

            text = str(result[1]).strip()
            confidence = float(result[2])

            if text and confidence >= self.min_confidence:
                candidates.append(text)

        return candidates
