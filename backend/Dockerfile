# Container image for hosting the photobooth backend (so you don't need a laptop
# running at the event). Builds everything including face recognition.
FROM python:3.11-slim

# System libs InsightFace/OpenCV and Pillow need at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + assets (background, attendee DB, fonts via the frontend folder).
COPY . .
# The frontend is served by the backend; copy it in too if building from repo root.
# (When building from backend/, mount or COPY ../frontend separately.)

EXPOSE 8000

# PUBLIC_HOST / FAL_KEY / OPENROUTER_API_KEY come from the host environment.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
