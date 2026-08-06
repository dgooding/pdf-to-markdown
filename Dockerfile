FROM python:3.9-slim

# Tesseract for optional OCR; pandoc not required
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from PyPI (Linux wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (see .dockerignore for exclusions)
COPY . .

EXPOSE 8000

# PORT env var set by hosting platform; DATA_ROOT for persistent published docs
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
