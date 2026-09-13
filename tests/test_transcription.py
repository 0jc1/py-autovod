import os
import sys

import numpy as np
import soundfile as sf

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


def test_transcription_does_not_import_pydub():
    assert not hasattr(transcription, "AudioSegment")
    assert "pydub" not in sys.modules


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
        "load_wav_samples",
        lambda p: (np.zeros(16000, dtype=np.int16), 16000),
    )
    monkeypatch.setattr(
        transcription, "extract_audio_features", lambda *a, **k: _fake_audio_features()
    )

    model = _FakeModel()
    transcription.transcribe_with_features(model, "audio.wav", "cuda", min_duration=999)

    assert len(model.calls) == 1
    assert model.calls[0].get("batch_size") == 16


def test_load_wav_samples_reads_int16_mono(tmp_path):
    path = tmp_path / "clip.wav"
    sample_rate = 16000
    samples = np.zeros(sample_rate, dtype=np.int16)
    samples[:100] = 1000
    sf.write(path, samples, sample_rate, subtype="PCM_16")

    loaded, loaded_sr = transcription.load_wav_samples(path)

    assert loaded_sr == sample_rate
    assert loaded.dtype == np.int16
    assert loaded.shape == (sample_rate,)
    assert loaded[0] == 1000


def test_extract_audio_features_silence_is_quiet():
    sample_rate = 16000
    samples = np.zeros(sample_rate, dtype=np.int16)

    features = transcription.extract_audio_features(samples, sample_rate, 0.0, 1.0)

    assert features["volume"]["level"] == "quiet"
    assert features["volume"]["value"] == 0.0
    assert features["characteristics"]["intensity"] == "normal"


def test_extract_audio_features_full_scale_sine_is_loud():
    sample_rate = 16000
    t = np.arange(sample_rate) / sample_rate
    samples = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)

    features = transcription.extract_audio_features(samples, sample_rate, 0.0, 1.0)

    assert features["volume"]["level"] == "loud"
    assert features["volume"]["value"] > 0.3


def test_extract_audio_features_empty_slice_is_quiet():
    samples = np.zeros(16000, dtype=np.int16)

    features = transcription.extract_audio_features(samples, 16000, 2.0, 3.0)

    assert features["volume"]["level"] == "quiet"
    assert features["volume"]["value"] == 0.0
    assert features["characteristics"]["zero_crossing_rate"] == 0.0
    assert features["characteristics"]["spectral_centroid"] == 0.0
