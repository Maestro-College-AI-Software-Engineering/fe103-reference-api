#!/bin/sh
# Start command for the Docker image (docker compose and Render both run it).
set -e

# 1. Create any missing tables.
flask --app taskapi init-db

# 2. Add the demo users and their tasks when SEED_DEMO_DATA=1 (safe to repeat).
if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
    flask --app taskapi seed
fi

# 3. Start the web server on every interface, on the port the host gives us.
exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --access-logfile - "taskapi:create_app('production')"
