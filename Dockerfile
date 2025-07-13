# Use Python 3.9 slim base image for smaller size
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create cache directory for FastF1 data
RUN mkdir -p /app/cache
ENV FASTF1_CACHE_DIR=/app/cache

# Expose port 8050 (Dash default)
EXPOSE 8050

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app_user
RUN chown -R app_user:app_user /app
USER app_user

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8050/ || exit 1

# Production command using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "1", "--timeout", "300", "app:server"]