import easyocr


class EasyOCRClient:
    """EasyOCR implementation of the OCR client interface."""

    def __init__(self, languages: list[str] | None = None) -> None:
        self.languages = languages or ["en"]
        self.reader = easyocr.Reader(self.languages, gpu=False)

    def read_text(self, image) -> list[str]:
        """Extract recognized text candidates from an image."""
        results = self.reader.readtext(image, detail=0, paragraph=False)
        return [text.strip() for text in results if text.strip()]
