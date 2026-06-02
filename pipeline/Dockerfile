FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pipeline/requirements.txt .
# Uncomment the following line if you want to include YOLO/Torch in the container image:
# RUN pip install --no-cache-dir ultralytics torch
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY pipeline/ ./pipeline/
COPY data/ ./data/

# Run the pipeline
# Note: we use API_URL=http://api:8000 to connect to the FastAPI container in docker-compose
CMD ["python", "-m", "pipeline.run", "--videos-dir", "./data", "--api-url", "http://api:8000", "--store-id", "STORE_BLR_002"]
