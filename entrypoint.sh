#!/bin/bash
set -e

rm -f /tmp/.X99-lock

echo "Starting X virtual framebuffer (Xvfb) in background..."
Xvfb -ac :99 -screen 0 1280x1024x16 &
export DISPLAY=:99

echo "Starting AutoVOD"
exec python src/main.py "$@"
