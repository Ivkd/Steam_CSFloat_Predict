FROM python:3.11-slim
WORKDIR /server

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    chromium \
    chromium-driver \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    fonts-liberation \
    xdg-utils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    asyncpg \
    python-dotenv \
    aiohttp \
    joblib \
    scikit-learn \
    pandas \
    numpy \
    lightgbm \
    selenium

COPY . .

EXPOSE 8000