FROM python:3.11-slim

# System deps for Camelot (Ghostscript/OpenCV libs) and Tabula (Java)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ghostscript \
    default-jre \
    gcc build-essential pkg-config \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps for the benchmark
COPY bench/requirements.txt /app/bench/requirements.txt
RUN pip install --no-cache-dir -r /app/bench/requirements.txt

# Copy the benchmark code (we also bind-mount at runtime)
COPY bench /app/bench

CMD ["bash"]
