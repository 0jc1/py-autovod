# Py-AutoVOD
[![MIT licensed](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED.svg?logo=docker&logoColor=white)](#)
[![Issues](https://img.shields.io/github/issues/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/issues)
[![Last Commit](https://img.shields.io/github/last-commit/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/commits/main)
[![Stars](https://img.shields.io/github/stars/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/stargazers)
[![Forks](https://img.shields.io/github/forks/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/network)

<b>Py-AutoVOD</b> is a Python3 program that automates the downloading and uploading of livestreams from multiple streaming services. It has many configurable features for stream VODs, such as formatting, transcribing, and AI-powered clipping.
This project was originally based on [AutoVOD](https://github.com/jenslys/AutoVOD).

## Features
- ( :heavy_check_mark: ) Auto download livestreams (Twitch.tv, Kick.tv, Youtube Live) from multiple streamers concurrently
- ( :heavy_check_mark: ) Audio transcription with timestamps
- ( :heavy_check_mark: ) Auto upload to RClone, YouTube, and more
- ( :heavy_check_mark: ) Smart AI video clipping
- ( :heavy_check_mark: ) Youtube shorts formatting
- ( :x: ) Archive both video and chat logs
- ( :heavy_check_mark: ) Platform independent and Docker supported

## Installation & Setup

1. Manually install ffmpeg and [streamlink](https://github.com/streamlink/streamlink). Alternatively, you can do the installation automatically with `install.sh`.

2. Python 3.10+ is required. Set up a Python virtual environment, then install the required packages:
   ```bash
   python -m venv env
   . env/bin/activate
   pip install -r requirements.txt
   ```
3. Install from source using pip.
   ```bash
   pip install -e .
   ```

4. Configure the streamers you want to monitor in `config.ini`:
   ```ini
   [streamers]
   streamers = streamer1, streamer2, streamer3
   ```

5. Create a configuration file for each streamer where the file name is the streamer's username. The default configuration file `default.ini` will be used otherwise.

6. Configure the main configuration file `config.ini`. Downloaded VODs are processed into clips by default.

7. Copy the `.env.example` file to a new file called `.env`. Fill in the .env file with your API keys.

8. Run the command to start AutoVOD:
   ```bash
   autovod
   ```

## Uploading

Auto uploading for YouTube works with [youtubeuploader](https://github.com/porjo/youtubeuploader), but it requires additional setup and configuration.

## Clip Generation

You can generate clips from a video file directly using a script.

Download an example video file from YouTube:

   ```bash
   python src/download_yt.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

   Run this command with the path to the video:
   ```bash
   python3 src/process_vid.py <path/to/video>
   ```

### Shorts Format
With ffmpeg you can convert mp4 into Youtube shorts format (9:16 aspect ratio):
```bash
ffmpeg -i input.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:a copy output.mp4
```

Add background music:
```bash
ffmpeg -i input.mp4 -i music.mp3 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v];[1:a]volume=0.3[a1];[0:a][a1]amix=inputs=2[a]" -map "[v]" -map "[a]" -shortest output.mp4
```

## Transcription

Audio transcription is done with OpenAI's Whisper ASR. This feature can be configured in `config.ini`

## Contribution

Contributors are welcome! Please feel free to submit a PR or issue.
