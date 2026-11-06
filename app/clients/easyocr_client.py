
import easyocr


class EasyOCRClient:
    """EasyOCR implementation with confidence filtering."""

    def __init__(self, languages: list[str] | None = None) -> None:
        self.languages = languages or ["en"]

        self.reader = easyocr.Reader(
            self.languages,
            gpu=False,
        )

    def read_text(self, image) -> list[str]:
        """Extract text candidates with reasonable OCR confidence."""

        results = self.reader.readtext(
            image,
            detail=1,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        )

        candidates = []

        for result in results:
            if len(result) < 3:
                continue

            text = result[1].strip()
            confidence = float(result[2])

            if confidence >= 0.25 and text:
                candidates.append(text)

        return candidates
