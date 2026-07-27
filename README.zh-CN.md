# Py-AutoVOD
[![MIT licensed](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED.svg?logo=docker&logoColor=white)](#)
[![Issues](https://img.shields.io/github/issues/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/issues)
[![Last Commit](https://img.shields.io/github/last-commit/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/commits/main)
[![Stars](https://img.shields.io/github/stars/0jc1/py-autovod.svg)](https://github.com/0jc1/py-autovod/stargazers)

<b>Py-AutoVOD</b> 是一个 Python3 程序，用于自动下载和上传来自多个流媒体服务的直播。它具有许多针对直播回放（VOD）的可配置功能，例如格式化、转录和 AI 驱动的片段截取。
本项目最初基于 [AutoVOD](https://github.com/jenslys/AutoVOD) 开发。

可以使用 [autovod.ai](https://autovod.ai) 体验免费的网页版。

## 功能
- ( :heavy_check_mark: ) 自动并发下载多个主播的直播（Twitch.tv, Kick.tv, Youtube Live）
- ( :heavy_check_mark: ) 带有时间戳的音频转录
- ( :heavy_check_mark: ) 自动上传至 RClone, YouTube 等平台
- ( :heavy_check_mark: ) 智能 AI 视频片段截取
- ( :heavy_check_mark: ) Youtube Shorts 格式化
- ( :x: ) 存档视频和聊天日志
- ( :heavy_check_mark: ) 平台无关且支持 Docker

## 安装与设置

1. 手动安装 ffmpeg 和 [streamlink](https://github.com/streamlink/streamlink)。或者，你可以通过 `install.sh` 进行自动安装。

2. 需要 Python 3.10+。设置 Python 虚拟环境，然后安装所需的包：
   ```bash
   python -m venv env
   . env/bin/activate
   pip install -r requirements.txt
   ```
3. 使用 pip 从源码安装。
   ```bash
   pip install -e .
   ```

4. 在 `config.ini` 中配置你想要监控的主播：
   ```ini
   [streamers]
   streamers = streamer1, streamer2, streamer3
   ```

5. 为每位主播创建配置文件，文件名即为主播的用户名。否则将使用默认配置文件 `default.ini`。

6. 配置主配置文件 `config.ini`。下载的 VOD 默认将被处理成片段（clips）。

7. 将 `.env.example` 文件复制为名为 `.env` 的新文件。在 .env 文件中填入你的 API 密钥。

8. 运行命令启动 AutoVOD：
   ```bash
   autovod
   ```

## 上传

YouTube 的自动上传功能通过 [youtubeuploader](https://github.com/porjo/youtubeuploader) 实现，但需要额外的设置和配置。

## 片段生成

你可以直接使用脚本从视频文件生成片段。

从 YouTube 下载示例视频文件：

   ```bash
   python src/download_yt.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

   使用视频路径运行此命令：
   ```bash
   python3 src/process_vid.py <path/to/video>
   ```

### Shorts 格式
使用 ffmpeg 你可以将 mp4 转换为 Youtube shorts 格式（9:16 宽高比）：
```bash
ffmpeg -i input.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:a copy output.mp4
```

添加背景音乐：
```bash
ffmpeg -i input.mp4 -i music.mp3 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v];[1:a]volume=0.3[a1];[0:a][a1]amix=inputs=2[a]" -map "[v]" -map "[a]" -shortest output.mp4
```

## 转录

音频转录使用 OpenAI 的 Whisper ASR 完成。此功能可以在 `config.ini` 中进行配置。

## 贡献

欢迎贡献者！请随时提交 PR 或 Issue。
