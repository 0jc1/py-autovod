FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/New_York \
    DISPLAY=:99

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    git \
    libgomp1 \
    libsndfile1 \
    tzdata \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Use CPU-only PyTorch packages to avoid installing CUDA dependencies.
RUN python -m pip install --no-cache-dir \
    torch torchaudio torchvision \
    --index-url https://download.pytorch.org/whl/cpu

COPY . .

# Install the project using pyproject.toml.
RUN python -m pip install --no-cache-dir -e . streamlink

# Handle Windows line endings.
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
