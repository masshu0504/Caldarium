# Base image
FROM postgres:15

# Install MinIO client and networking tools
RUN apt-get update && apt-get install -y \
    wget \
    bash \
    ca-certificates \
    unzip \
    iputils-ping \
    netcat-openbsd \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install mc (MinIO client)
RUN wget https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc

# Set working directory
WORKDIR /workspace

# Default command
CMD ["bash"]
