import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_parse_comma_separated_values():
    settings = Settings(
        vehicle_classes="Car, bus ,",
        ocr_languages="en,ur",
        allowed_video_extensions="mp4,.MOV",
        cors_origins="http://a.test, http://b.test",
        max_upload_size_mb=2,
    )

    assert settings.vehicle_class_names == {"car", "bus"}
    assert settings.ocr_language_list == ["en", "ur"]
    assert settings.video_extensions == {".mp4", ".mov"}
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]
    assert settings.max_upload_size_bytes == 2 * 1024 * 1024


def test_settings_reject_line_2_above_line_1():
    with pytest.raises(ValidationError):
        Settings(line_1_y=500, line_2_y=300)
