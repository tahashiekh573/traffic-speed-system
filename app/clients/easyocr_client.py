"""EasyOCR wrapper used by the plate recognition agent."""

import cv2
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
        max_image_width: int = 360,
    ) -> None:
        self.languages = languages or ["en"]
        self.min_confidence = min_confidence
        self.max_image_width = max_image_width
        self.reader = easyocr.Reader(self.languages, gpu=use_gpu, verbose=False)

    def _limit_size(self, image: np.ndarray) -> np.ndarray:
        """Shrink large crops: OCR time grows with the pixel count."""
        width = image.shape[1]
        if width <= self.max_image_width:
            return image
        scale = self.max_image_width / width
        return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    def read_text(self, image: np.ndarray) -> list[str]:
        """Return text candidates whose OCR confidence passes the threshold."""
        image = self._limit_size(image)

        results = self.reader.readtext(
            image,
            detail=1,
            paragraph=False,
            allowlist=PLATE_ALLOWLIST,
            canvas_size=max(image.shape[:2]) + 32,
            mag_ratio=1.0,
            batch_size=4,
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
