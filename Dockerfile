FROM python:3.11-slim

# ffmpeg for the render/offline-provider toolchain; fonts-dejavu-core gives
# ffmpeg's drawtext/ass filters a real font file via fontfile=/fontsdir=,
# sidestepping the fontconfig-not-configured failure documented in
# app/render/ffmpeg.py (found by actually running a render, not by reading
# docs). app/server/startup_checks.py fails fast at process startup if
# either is somehow still missing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY pyproject.toml .
COPY app/ app/
COPY prompts/ prompts/
COPY assets/ assets/

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "app.cli", "--help"]
