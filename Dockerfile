FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data

# Set environment variables directly
ENV HOST=0.0.0.0
ENV PORT=8002
ENV DEBUG=false

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the application
CMD ["python", "main.py"]
