FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY taskapi ./taskapi
COPY start.sh .

ENV APP_CONFIG=production \
    PORT=8000
EXPOSE 8000

# start.sh creates the tables, seeds the demo data if SEED_DEMO_DATA=1, then runs
# gunicorn --bind 0.0.0.0:${PORT:-8000} "taskapi:create_app('production')"
CMD ["sh", "start.sh"]
