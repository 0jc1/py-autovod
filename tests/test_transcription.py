import os
import sys
import types

# Add src to path to import transcription
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Other test modules (e.g. test_processor) stub out ``transcription`` in
# ``sys.modules`` to keep their imports lightweight. Drop any such stub so we
# always exercise the real module here, regardless of collection order.
sys.modules.pop("transcription", None)
import transcription  # noqa: E402


def _fake_audio_features():
    return {
        "volume": {"level": "normal", "value": 0.2},
        "characteristics": {
            "intensity": "normal",
            "zero_crossing_rate": 0.1,
            "spectral_centroid": 1000.0,
        },
    }


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    """Stand-in for a faster-whisper model / batched pipeline."""

    def __init__(self):
        self.calls = []

    def transcribe(self, audio_path, **kwargs):
        self.calls.append(kwargs)
        return iter([_FakeSegment(0.0, 1.0, "hello")]), object()


def test_build_faster_whisper_model_plain(monkeypatch):
    """Without batching, the raw WhisperModel is returned unwrapped."""
    sentinel = object()
    monkeypatch.setattr(transcription, "batched", False)
    monkeypatch.setattr(transcription, "WhisperModel", lambda *a, **k: sentinel)

    wrapped = {}
    monkeypatch.setattr(
        transcription,
        "BatchedInferencePipeline",
        lambda model: wrapped.setdefault("model", model),
    )

    result = transcription.build_faster_whisper_model("cpu")

    assert result is sentinel
    assert "model" not in wrapped


def test_transcribe_passes_batch_size_when_batched(monkeypatch):
    monkeypatch.setattr(transcription, "transcription_engine", "faster-whisper")
    monkeypatch.setattr(transcription, "batched", True)
    monkeypatch.setattr(transcription, "batch_size", 16)
    monkeypatch.setattr(transcription, "language", "en")
    monkeypatch.setattr(
        transcription,
        "AudioSegment",
        types.SimpleNamespace(from_wav=lambda p: object()),
    )
    monkeypatch.setattr(
        transcription, "extract_audio_features", lambda *a, **k: _fake_audio_features()
    )

    model = _FakeModel()
    transcription.transcribe_with_features(model, "audio.wav", "cuda", min_duration=999)

    assert len(model.calls) == 1
    assert model.calls[0].get("batch_size") == 16
