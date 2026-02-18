# SentinelAI Backend Dockerfile for Render
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY . .

# Expose port (Render uses PORT env var)
EXPOSE 10000

# Default environment variables
ENV PORT=10000
ENV MODULE=school

# Run the application
CMD ["sh", "start.sh"]
