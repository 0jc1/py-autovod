import os
import platform
import subprocess
from utils import run_command
from logger import logger

YOUTUBE_UPLOADER_LINUX = "/root/youtubeuploader/youtubeuploader"
YOUTUBE_UPLOADER_WINDOWS = "C:\\youtubeuploader\\youtubeuploader.exe"


def upload_youtube(filename: str) -> None:
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"File not found: {filename}")

    if platform.system() == "Windows":
        uploader_path = YOUTUBE_UPLOADER_WINDOWS
        filename = os.path.normpath(filename)
    else:
        uploader_path = YOUTUBE_UPLOADER_LINUX

    if not os.path.isfile(uploader_path):
        cwd_uploader = os.path.join(os.getcwd(), os.path.basename(uploader_path))
        if os.path.isfile(cwd_uploader):
            uploader_path = cwd_uploader
        else:
            raise FileNotFoundError(
                f"YouTube uploader not found in either {uploader_path} or {cwd_uploader}"
            )

    command = [uploader_path, "-filename", filename]
    result = run_command(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = result.stdout.decode().strip()
    if stdout:
        logger.info(stdout)

    if result.returncode != 0:
        raise RuntimeError("youtubeuploader failed to upload the file")
