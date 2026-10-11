FROM python:3.11-slim

# Install compilation tools needed for liboqs (Open Quantum Safe C library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
RUN pip install --no-cache-dir \
    liboqs-python \
    pika \
    web3 \
    cryptography \
    numpy \
    requests \
    python-dotenv

# Pre-compile liboqs inside the image layer for instant runtime startup
RUN python -c "import oqs; print('liboqs precompiled successfully')"

# Copy project files
COPY . /app

# Run server.py unbuffered by default
CMD ["python", "-u", "server.py"]
