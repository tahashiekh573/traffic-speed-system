from app.core.config import Settings


def test_helmet_class_names_are_normalised():
    settings = Settings(
        helmet_class_names="With Helmet",
        no_helmet_class_names="Without-Helmet, head",
    )

    assert settings.helmet_labels == {"withhelmet"}
    assert settings.no_helmet_labels == {"withouthelmet", "head"}
    assert Settings.normalize_label("No_Helmet") == "nohelmet"


def test_onnx_helmet_model_without_runtime_fails_clearly(tmp_path, monkeypatch):
    """Never let Ultralytics auto-install onnxruntime behind the user's back."""
    import pytest

    from app.clients import helmet_detector_client as module

    model = tmp_path / "helmet.onnx"
    model.write_bytes(b"not-a-real-model")
    monkeypatch.setattr(module, "_has_module", lambda name: False)

    with pytest.raises(ImportError, match="onnxruntime"):
        module.HelmetDetectorClient(Settings(helmet_model_path=model))
