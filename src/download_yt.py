#!/usr/bin/env python3
"""
YouTube Video Downloader

This script downloads YouTube videos from a provided URL.
Usage: python download_yt.py [YouTube URL]
"""

import sys
import os
import argparse

# Import yt-dlp here to avoid import error if not installed
try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed.")
    print("Please install it using: pip install yt-dlp")

# ffmpeg -i input.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,blur=20[bg];[bg][0:v]scale=1080:1920:force_original_aspect_ratio=decrease[scaled];[scaled]pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1" -c:a copy output.mp4

# Force og aspect ratio
# ffmpeg -i input.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1" -c:a copy output.mp4

# ffmpeg -i input.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:a copy output.mp4


def parse_arguments():
    parser = argparse.ArgumentParser(description="Download YouTube videos")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-o", "--output", help="Output directory", default="downloads")
    parser.add_argument(
        "-f", "--format", help="Video format (default: best)", default="best"
    )
    return parser.parse_args()


def download_video(url, output_dir, format_option):
    """
    Download a YouTube video using yt-dlp.

    Args:
        url: YouTube video URL
        output_dir: Directory to save the downloaded video
        format_option: Video format option

    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        # Configure yt-dlp options
        ydl_opts = {
            "extractor-arg": "youtube:player_client=web_safari",
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",  # Ensures final output is MP4
            "quiet": False,
            "progress": True,
            "no_warnings": False,
            "restrictfilenames": True,  # Avoids special characters in filenames
        }

        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading video from: {url}")
            ydl.download([url])

        print(f"Video downloaded successfully to {output_dir}")
        return True

    except Exception as e:
        print(f"Error downloading video: {e}")
        return False


def main():
    args = parse_arguments()

    if not args.url.startswith(("http://", "https://")):
        print("Error: Please provide a valid URL starting with http:// or https://")
        sys.exit(1)

    # Download the yt video
    success = download_video(args.url, args.output, args.format)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
