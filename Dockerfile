# Python base image
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

WORKDIR /app

# System dependencies (normalise browser WebM recordings into playable MP3 files)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Project
COPY . ./

# Collect static (optional, requires settings STATIC_ROOT)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

CMD ["gunicorn", "App_PADESCE.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "180", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-"]
