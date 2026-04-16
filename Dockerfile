FROM python:3.11-slim

# Install system deps: Chromium for Selenium, Tesseract for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Chromium paths for Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Screenshots directory for headless review
RUN mkdir -p /app/static/screenshots

EXPOSE 5000

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --timeout 120"]
