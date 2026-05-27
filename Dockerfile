FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright
RUN playwright install chromium

# Copy application code
COPY . .

# Railway injects PORT env var — default to 8080
EXPOSE 8080

# Launch the web dashboard (which controls the bot)
CMD ["python", "server.py"]
