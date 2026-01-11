# Use the official Python executable using the slim version for a smaller image size
FROM python:3.12-slim

# Prevent Python from buffering stdout and stderr (for logging)
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# gcc and python3-dev might be needed for some python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy the rest of the application code
COPY . .

# Change ownership of the application directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port (Cloud Run sets the PORT env var, defaulting to 8080)
# Note: This is documentation only, the app must bind to the environment variable
EXPOSE 8080

# Run gunicorn
# 1 worker, 8 threads is a good starting point for I/O bound Flask apps on Cloud Run
# 0 timeout is required by Cloud Run to avoid killing long connections prematurely
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
