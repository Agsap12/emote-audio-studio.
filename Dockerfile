# Emote Audio Studio - 24/7 Cloud Dockerfile (Render / Railway / HuggingFace)
FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Setup environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    EAS_CLOUD=1 \
    PORT=8765

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure downloads directory exists and has permissions
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# Expose port
EXPOSE 8765

# Start Emote Audio Studio
CMD ["python", "app.py"]

