# Use Python 3.11 slim as base image for optimal size and performance
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for image processing
RUN apt-get update && apt-get install -y \
    curl \
    libgl1-mesa-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/generated /app/static /app/templates

# Create persistent volume mount point
RUN mkdir -p /logs

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Expose port 5000
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run the application
CMD ["python", "app.py"]
