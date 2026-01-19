# Import handling for Whisper with compatibility checks
import sys

try:
    import torch
except ImportError:
    print("ERROR: PyTorch is required. Please install with:")
    print("pip install torch torchaudio")
    sys.exit(1)

# Standard imports
from pathlib import Path
import json
import subprocess
import time
import numpy as np
from pydub import AudioSegment
import librosa
from settings import config

transcription_engine = config.get("clipception.transcription", "engine", fallback="whisper")

if transcription_engine == "faster-whisper":
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("ERROR: faster-whisper is not installed.")
        sys.exit(1)
else:
    try:
        import whisper
    except ImportError:
        print("ERROR: Whisper is not installed.")
        sys.exit(1)

# Global list for cleanup
files_to_cleanup = []
MIN_DURATION = config.getfloat("clipception", "clip_duration")
model_size = config.get("clipception.transcription", "model_size")
device = config.get("clipception.transcription", "device")


def format_time(seconds):
    """Convert seconds into human readable time string"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"


def check_cuda():
    if torch.cuda.is_available():
        try:
            # Basic CUDA functionality test
            test_tensor = torch.tensor([1.0]).cuda()
            del test_tensor
            torch.cuda.empty_cache()
            return True
        except Exception as e:
            print(f"CUDA available but failed to initialize: {str(e)}")
            return False
    return False


def extract_audio_features(audio_segment, start_time, end_time):
    """Extract audio features for a segment including volume and characteristics"""
    start_sample = int(start_time * 1000)
    end_sample = int(end_time * 1000)
    segment = audio_segment[start_sample:end_sample]

    samples = np.array(segment.get_array_of_samples())

    # Audio analysis
    rms = librosa.feature.rms(y=samples.astype(float))[0]
    zero_crossing_rate = librosa.feature.zero_crossing_rate(samples.astype(float))[0]
    spectral_centroid = librosa.feature.spectral_centroid(
        y=samples.astype(float), sr=segment.frame_rate
    )[0]

    avg_volume = float(np.mean(rms))
    avg_zcr = float(np.mean(zero_crossing_rate))
    avg_spectral_centroid = float(np.mean(spectral_centroid))

    # Volume classification
    if avg_volume < 0.1:
        volume_level = "quiet"
    elif avg_volume < 0.3:
        volume_level = "normal"
    else:
        volume_level = "loud"

    # Intensity classification
    intensity = "high" if avg_zcr > 0.15 and avg_spectral_centroid > 2000 else "normal"

    return {
        "volume": {"level": volume_level, "value": avg_volume},
        "characteristics": {
            "intensity": intensity,
            "zero_crossing_rate": avg_zcr,
            "spectral_centroid": avg_spectral_centroid,
        },
    }


def extract_audio(video_path):
    video_file = Path(video_path)
    audio_path = video_file.with_suffix(".wav")

    print(f"Extracting audio to {audio_path}...")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_file),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(audio_path),
        ],
        check=True,
    )

    global files_to_cleanup
    files_to_cleanup.append(str(audio_path))
    return audio_path


def combine_segments(segments):
    """Combine multiple segments into a single segment with merged features"""
    if not segments:
        return None

    combined_text = " ".join(seg["text"].strip() for seg in segments)

    start_time = segments[0]["start"]
    end_time = segments[-1]["end"]

    # Aggregate features
    volumes = [seg["audio_features"]["volume"]["value"] for seg in segments]
    zcrs = [
        seg["audio_features"]["characteristics"]["zero_crossing_rate"]
        for seg in segments
    ]
    centroids = [
        seg["audio_features"]["characteristics"]["spectral_centroid"]
        for seg in segments
    ]

    avg_volume = np.mean(volumes)
    avg_zcr = np.mean(zcrs)
    avg_centroid = np.mean(centroids)

    # Classify combined features
    volume_level = (
        "loud" if avg_volume >= 0.3 else "normal" if avg_volume >= 0.1 else "quiet"
    )
    intensity = "high" if avg_zcr > 0.15 and avg_centroid > 2000 else "normal"

    return {
        "start": start_time,
        "end": end_time,
        "text": combined_text,
        "audio_features": {
            "volume": {"level": volume_level, "value": float(avg_volume)},
            "characteristics": {
                "intensity": intensity,
                "zero_crossing_rate": float(avg_zcr),
                "spectral_centroid": float(avg_centroid),
            },
        },
    }


def transcribe_with_features(model, audio_path, device: str, min_duration=MIN_DURATION):
    """Get transcription with timestamps and audio features"""
    print("Generating enhanced transcription...")
    enhanced_segments = []

    audio = AudioSegment.from_wav(str(audio_path))

    transcribe_start = time.time()

    # Transcribe based on engine type
    if transcription_engine == "faster-whisper":
        # faster-whisper returns segments directly
        segments, info = model.transcribe(str(audio_path), language="en")
        result = {"segments": list(segments)}
    else:
        # Original whisper with FP16 support
        fp16 = device == "cuda" and torch.cuda.is_bf16_supported()
        if device == "cuda":
            torch.cuda.init()
        result = model.transcribe(str(audio_path), language="en", fp16=fp16)

    current_segments = []
    current_duration = 0.0

    for segment in result["segments"]:
        # Handle both faster-whisper (object attributes) and whisper (dict access)
        start = segment.start if hasattr(segment, 'start') else segment["start"]
        end = segment.end if hasattr(segment, 'end') else segment["end"]
        text = segment.text if hasattr(segment, 'text') else segment["text"]
        
        audio_features = extract_audio_features(audio, start, end)

        enhanced_segment = {
            "start": start,
            "end": end,
            "text": text,
            "audio_features": audio_features,
        }

        current_segments.append(enhanced_segment)
        current_duration = current_segments[-1]["end"] - current_segments[0]["start"]

        if current_duration >= min_duration:
            combined_segment = combine_segments(current_segments)
            if combined_segment:
                enhanced_segments.append(combined_segment)
            current_segments = []
            current_duration = 0.0

    if current_segments:
        combined_segment = combine_segments(current_segments)
        if combined_segment:
            enhanced_segments.append(combined_segment)

    transcribe_end = time.time()
    print(
        f"Enhanced transcription processing took: {format_time(transcribe_end - transcribe_start)}"
    )

    return enhanced_segments


def process_video(video_path):
    global device

    device = "cpu" if not check_cuda() else device
    
    process_start = time.time()
    video_file = Path(video_path)
    transcription_path = video_file.with_suffix(".enhanced_transcription.json")

    try:
        # Audio extraction
        audio_path = extract_audio(video_path)

        # Model loading
        print(f"Loading {transcription_engine} {model_size} model for {device}...")
        if transcription_engine == "faster-whisper":
            model = WhisperModel(model_size, device=device, compute_type="float16" if device == "cuda" else "float32")
        else:
            model = whisper.load_model(model_size, device=device)
            # Verify model device
            print(f"Model is on device: {next(model.parameters()).device}")


        if device == "cuda":
            print(f"GPU Memory allocated: {torch.cuda.memory_allocated()/1024**2:.2f} MB")
            print(f"GPU Memory reserved: {torch.cuda.memory_reserved()/1024**2:.2f} MB")

        # Transcription
        enhanced_transcription = transcribe_with_features(model, audio_path, device)

        # Save results
        with open(transcription_path, "w", encoding="utf-8") as f:
            json.dump(enhanced_transcription, f, indent=2, ensure_ascii=False)

        process_end = time.time()
        print(f"\n{'='*40}")
        print(f"Total processing time: {format_time(process_end - process_start)}")
        print(f"Enhanced transcription saved to {transcription_path}")
        print(f"{'='*40}")

    except Exception as e:
        print(f"\n{'!'*40}")
        print(f"Error processing video: {str(e)}")
        print(f"{'!'*40}")
        raise
    finally:
        # Cleanup operations
        if device == "cuda":
            torch.cuda.empty_cache()
