# Import handling for Whisper with compatibility checks
try:
    import torch
except ImportError:
    print("ERROR: PyTorch is required. Please install with:")
    print("pip install torch torchaudio")
    import sys

    sys.exit(1)

print("Imported torch")

try:
    import whisper
    from whisper import load_model
except ImportError:
    print("ERROR: Whisper is not installed. Please install with:")
    print("pip install openai-whisper")
    import sys

    sys.exit(1)

print("Imported whipser ")

# Standard imports
from pathlib import Path
import json
import argparse
import subprocess
import time
import numpy as np
from datetime import timedelta
from pydub import AudioSegment
import librosa
import soundfile as sf
import os
import atexit
import sys

# Global list for cleanup
files_to_cleanup = []


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


def transcribe_with_features(model, audio_path, device: str, min_duration=15.0):
    """Get transcription with timestamps and audio features"""
    print("Generating enhanced transcription...")
    enhanced_segments = []

    audio = AudioSegment.from_wav(str(audio_path))

    transcribe_start = time.time()

    # Configure FP16 based on CUDA support
    fp16 = device == "cuda" and torch.cuda.is_bf16_supported()

    result = model.transcribe(str(audio_path), language="en", fp16=fp16)

    current_segments = []
    current_duration = 0.0

    for segment in result["segments"]:
        audio_features = extract_audio_features(audio, segment["start"], segment["end"])

        enhanced_segment = {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],
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


def cleanup_files():
    """Clean up temporary files created during processing"""
    pass
    # global files_to_cleanup
    # print("\nCleaning up temporary files...")
    # for file_path in files_to_cleanup:
    #     try:
    #         if os.path.exists(file_path):
    #             os.unlink(file_path)
    #             print(f"Removed file: {file_path}")
    #     except Exception as e:
    #         print(f"Warning: Failed to remove {file_path}: {e}")


def process_video(video_path, model_size="base"):
    process_start = time.time()

    # Device configuration
    device = "cuda" if check_cuda() else "cpu"
    print(f"\n{'='*40}")
    print(f"Processing on: {device.upper()}")
    print(f"{'='*40}\n")

    video_file = Path(video_path)
    transcription_path = video_file.with_suffix(".enhanced_transcription.json")

    try:
        # Audio extraction
        audio_path = extract_audio(video_path)

        # Model loading
        print(f"Loading Whisper {model_size} model...")
        model = whisper.load_model(model_size).to(device)

        if device == "cuda":
            print(
                f"GPU Memory allocated: {torch.cuda.memory_allocated()/1024**2:.2f} MB"
            )
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
        cleanup_files()


if __name__ == "__main__":
    # Register cleanup handler
    atexit.register(cleanup_files)

    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Process video with enhanced Whisper transcription"
    )
    parser.add_argument(
        "--input", type=str, help="Path to the video file to process"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: Input file {args.input} not found!")
        sys.exit(1)

    try:
        process_video(args.input, args.model)
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user!")
        sys.exit(1)
    except Exception as e:
        print(f"\nCritical error occurred: {str(e)}")
        sys.exit(1)
