# fe103-reference-api

A small, working task API for FE103. You can build your React frontend against it.

It follows the same conventions as the API you built in BE106:
- a Flask application factory;
- JWT Bearer login;
- one user-owned resource with CRUD and pagination;
- one error shape.

It also has **CORS** turned on, so a React app running in the browser can call it.

**Use your own BE106 API if it works.** This repository is the fallback. Use it if your API is broken, or while you fix it. The FE103 lessons work against either one.

Small differences between the two APIs are fine: your API might have `events` instead of `tasks`, or a different pagination shape. Your endpoint map records what your frontend actually calls.

## Quick start

Pick one of the two options. Both serve the API at **http://localhost:8000**, which is the base URL your frontend uses (for example, `VITE_API_URL=http://localhost:8000` in the frontend's `.env`).

### Option A: Docker (the same setup as production)

You need Docker Desktop, as in BE106.

```bash
cd fe103-reference-api
cp .env.example .env        # then put a long random string in JWT_SECRET
docker compose up --build
```

The first start does four things:
1. builds the image;
2. starts Postgres;
3. creates the tables;
4. adds the [demo users](#demo-users).

When the logs show `Listening at: http://0.0.0.0:8000`, open a second terminal:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

To stop, press Ctrl+C or run `docker compose down`. Your data survives. `docker compose down -v` also deletes the database volume, and the demo data comes back on the next `up`.

### Option B: a virtual environment with SQLite

You need Python 3.9 or newer. Python 3.12, the version in the Docker image, is recommended.

```bash
cd fe103-reference-api
python3 -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # then put a long random string in JWT_SECRET
flask --app taskapi seed             # creates instance/taskapi.db and the demo users
flask --app taskapi run --port 8000
```

We use `--port 8000` for two reasons:
- both options then have the same address;
- Flask's default port, 5000, is taken on macOS by AirPlay Receiver.

Add `--debug` to reload the server when you change the code.

To start over, you have two choices:
- delete `instance/taskapi.db` to remove everything;
- run `flask --app taskapi seed --reset` to restore only the demo users and their tasks.

To make a random secret for `JWT_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Demo users

| Username | Password | Tasks | Use it for |
|---|---|---|---|
| `demo` | `demo-password-1` | 25: some done, some not; some with due dates | Your main test account. 3 pages at `per_page=10`. |
| `other` | `other-password-1` | 3 | The "not yours" case. `demo` gets **403** on these tasks. |

About the seed data:
- **Task ids.** On a fresh database, demo's tasks are ids 1-25 and other's are ids 26-28. `flask seed` prints the ids.
- **Due dates** are counted from the day you seed, so some tasks are overdue and some are upcoming.
- **Running it again.** `flask seed` never duplicates anything and leaves existing demo users alone. `--reset` deletes and recreates them.
- **Docker** runs `flask seed` at every start, because `SEED_DEMO_DATA=1` in `docker-compose.yml`.
- **Deploying.** These passwords are public. If you deploy this API and don't want anyone logging in as `demo`, set `SEED_DEMO_DATA=0`.

## API contract

These rules apply to every endpoint:
- **Bodies are JSON.** Send `Content-Type: application/json` with every request that has a body.
- **Auth.** "Bearer" in the Auth column means the request needs the header `Authorization: Bearer <access_token>`, using the token from `/auth/login`.
- **401** in the Errors column means `missing_token`, `invalid_token` or `token_expired` (see [Errors](#errors)).
- **Invalid body.** Any endpoint that takes a body can also answer `400 invalid_json`.

| Method | Path | Auth | Request body | Success | Errors |
|---|---|---|---|---|---|
| GET | `/health` | none | none | `200` `{"status": "ok"}` | none |
| POST | `/auth/register` | none | `{"username", "password"}` | `201` `{"id", "username"}` | `400 validation_error` (fields: `username`, `password`), `409 username_taken` |
| POST | `/auth/login` | none | `{"username", "password"}` | `200` `{"access_token", "token_type": "Bearer", "expires_in": 3600}` | `400 validation_error`, `401 invalid_credentials` (same message for a wrong username or a wrong password) |
| GET | `/users/me` | Bearer | none | `200` `{"id", "username", "display_name"}` | 401 |
| PATCH | `/users/me` | Bearer | `{"display_name"}` (a string, or `null` to clear it) | `200` `{"id", "username", "display_name"}` | `400 validation_error`, 401 |
| GET | `/tasks?page=1&per_page=10` | Bearer | none | `200` `{"items": [task, ...], "page", "per_page", "total", "pages"}` | `400 validation_error` (fields: `page`, `per_page`), 401 |
| POST | `/tasks` | Bearer | `{"title", "description"?, "done"?, "due_date"?}` | `201` task | `400 validation_error`, 401 |
| GET | `/tasks/<id>` | Bearer | none | `200` task | 401, `403 forbidden`, `404 not_found` |
| PATCH | `/tasks/<id>` | Bearer | any of `title`, `description`, `done`, `due_date` | `200` task (updated) | `400 validation_error`, 401, `403 forbidden`, `404 not_found` |
| DELETE | `/tasks/<id>` | Bearer | none | `204` (empty body) | 401, `403 forbidden`, `404 not_found` |

### The task object

```json
{
  "id": 1,
  "title": "Pick the app idea and write the scope",
  "description": "In: tasks with due dates. Out: sharing.",
  "done": true,
  "due_date": "2026-09-17",
  "created_at": "2026-09-29T23:23:05Z",
  "owner_id": 1
}
```

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Set by the server. |
| `title` | string | Required when creating. 1-120 characters; spaces at the ends are trimmed. |
| `description` | string or `null` | Optional, at most 1000 characters. `""` is stored as `null`. |
| `done` | boolean | Optional, default `false`. Must be `true` or `false` (not `"true"`, not `1`). |
| `due_date` | `"YYYY-MM-DD"` or `null` | Optional. Must be a real date. `""` (an empty date input) is stored as `null`. |
| `created_at` | string | Set by the server. UTC, ISO 8601, for example `"2026-09-29T23:23:05Z"`. |
| `owner_id` | integer | Always the logged-in user, taken from the token. Ignored if you send it. |

Keys that aren't task fields, such as `id` or `owner_id`, are ignored in POST and PATCH bodies. A PATCH that contains none of the four task fields gets `400 validation_error`.

### Users and passwords

- **`username`:** 3-30 characters. Spaces at the ends are trimmed, and usernames are case-sensitive (`Demo` is not `demo`).
- **`password`:** 8-128 characters. The API stores only a hash (werkzeug `generate_password_hash`), never the password itself.
- **`display_name`:** 1-60 characters, or `null`. It is `null` until you set it with `PATCH /users/me`. `PATCH /users/me` changes only `display_name` and ignores any other keys.

### Tokens

- **Format:** a JWT signed with HS256 and `JWT_SECRET`.
- **`sub`:** the user id **as a string** (for example `"1"`). The server turns it back into a number with `int()`.
- **Lifetime:** `TOKEN_TTL_MINUTES` (default 60). `expires_in` in the login response is the same lifetime in seconds.
- **No refresh tokens.** When a request answers `401 token_expired`, send the user back to the login page.

### Pagination

- **Parameters:** `GET /tasks?page=2&per_page=10`. The defaults are `page=1` and `per_page=10`; `per_page` can be at most 50.
- **What you get:** only your own tasks, ordered by `id` (oldest first).
- **`pages`:** the number of pages (0 when you have no tasks).
- **A page past the end** returns `200` with `"items": []`. It is not an error.
- **Bad values** (`page=0`, `per_page=51`, `per_page=abc`) return `400 validation_error`, with `fields.page` or `fields.per_page`.

### 403 or 404 for someone else's task?

This API answers:
- `403 forbidden` when the task exists but belongs to another user;
- `404 not_found` when no task has that id.

Some APIs answer 404 in both cases, so they never reveal which ids exist. Your own BE106 API may be one of them. Both are valid choices, and your frontend should handle both.

### Errors

Every error, from any endpoint, has the same shape:

```json
{"error": {"code": "not_found", "message": "Task 999 does not exist."}}
```

Validation errors (400) add a `fields` object with one message per bad field, so a form can show each message next to its input:

```json
{"error": {"code": "validation_error",
           "message": "Some fields are invalid. See 'fields' for details.",
           "fields": {"title": "cannot be blank", "due_date": "must be a date in YYYY-MM-DD format, or null"}}}
```

Your code should branch on `code`, which is stable. `message` is for people and may change.

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_json` | The body is missing, isn't JSON, or isn't a JSON object. Usually the `Content-Type: application/json` header is missing. |
| 400 | `validation_error` | A field or query parameter is wrong. See `fields`. |
| 401 | `missing_token` | No `Authorization` header. |
| 401 | `invalid_token` | The header isn't `Bearer <token>`, or the token was changed, signed with another secret, or its user no longer exists. |
| 401 | `token_expired` | The token is older than `TOKEN_TTL_MINUTES`. Log in again. |
| 401 | `invalid_credentials` | Login with a wrong username or password. |
| 403 | `forbidden` | The task belongs to another user. |
| 404 | `not_found` | No task has that id, or no route matches the path. |
| 405 | `method_not_allowed` | The method is wrong for this path. The `Allow` header lists the right ones. |
| 409 | `username_taken` | Registering a username that already exists. |
| 413 | `request_entity_too_large` | The body is over 1 MB. |
| 500 | `internal_error` | A bug or a database problem. Check the server logs. |

## Try it with curl

These examples use `http://localhost:8000`. On Windows, run them in WSL, as in BE106. The outputs are shortened.

```bash
# Register a new user
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "maya", "password": "maya-password-1"}'
# 201  {"id":3,"username":"maya"}

# Log in as demo
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo-password-1"}'
# {"access_token":"eyJhbGciOi...","token_type":"Bearer","expires_in":3600}

# The same login, keeping the token in a shell variable for the next commands
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo-password-1"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# List page 1 of demo's tasks
curl -s "http://localhost:8000/tasks?page=1&per_page=10" -H "Authorization: Bearer $TOKEN"
# {"items":[{"id":1,...},...,{"id":10,...}],"page":1,"per_page":10,"total":25,"pages":3}

# Create a task
curl -i -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Call the API from React", "due_date": "2026-10-15"}'
# 201  {"id":29,"title":"Call the API from React","description":null,"done":false,
#       "due_date":"2026-10-15","created_at":"2026-09-29T23:23:28Z","owner_id":1}

# Someone else's task (other's first task on a fresh database)
curl -i http://localhost:8000/tasks/26 -H "Authorization: Bearer $TOKEN"
# 403  {"error":{"code":"forbidden","message":"This task belongs to another user."}}
```

## CORS: calling this API from a browser

A browser lets a page read a response from a different **origin** only if the API says that origin is allowed. An origin is the scheme, host and port together. Your Vite dev server (`http://localhost:5173`) and this API (`http://localhost:8000`) are different origins.

**What this API does:**
- `CORS_ORIGINS` lists the allowed origins. The default is `http://localhost:5173`, so a Vite dev server can call this API directly.
- It allows the `Authorization` and `Content-Type` headers.
- It allows the methods `GET`, `POST`, `PATCH`, `DELETE` and `OPTIONS`.
- It answers the browser's preflight (`OPTIONS`) request.
- Error responses carry the CORS headers too, so your frontend can read the body of a 401 or a 400.

**Using the Vite dev proxy?** Then the browser only talks to `localhost:5173`, and CORS isn't involved locally. Set the proxy target to `http://127.0.0.1:8000` (see [Troubleshooting](#troubleshooting)).

**Deployed frontend:** add its exact origin, separated by a comma:

```bash
CORS_ORIGINS=http://localhost:5173,https://my-frontend.onrender.com
```

- The scheme, host and port must match exactly. `http://localhost:5173` and `http://127.0.0.1:5173` are different origins, and so are `http://` and `https://`.
- Don't include a path. A trailing slash is removed for you.
- `npm run preview` serves at `http://localhost:4173`. Add that origin too if you use it.
- Restart the API after changing `CORS_ORIGINS`. On Render, saving the environment variables redeploys the service.

**What a CORS failure looks like:**
- The browser console says the request `has been blocked by CORS policy`.
- `fetch` rejects with `TypeError: Failed to fetch`.

The request may still have reached the API, so check the Network tab and the API's logs.

## Deploy on Render

Render can build this repository's `Dockerfile` as a Web Service, the same way you deployed your API in BE106.

1. **Create a Postgres database.** Use the Neon free tier, as in BE106, and copy its connection string. A `postgresql://...` URL works as it is, because the app switches it to the psycopg driver. Keep `?sslmode=require` at the end.
2. **Create the service.** On Render, choose **New > Web Service** and connect your copy of this repository (a fork, or its public URL). Render detects the Dockerfile. Choose the free instance type.
3. **Add the environment variables:**
   - `DATABASE_URL`: the Neon connection string.
   - `JWT_SECRET`: a long random string.
   - `CORS_ORIGINS`: your deployed frontend's origin. Add `http://localhost:5173` as well if you still run the frontend locally against this API.
   - `SEED_DEMO_DATA`: `1` if you want the demo users.

   Leave `PORT` alone; Render sets it.
4. **Set the health check path** to `/health`.
5. **Deploy**, then run `curl https://<your-service>.onrender.com/health`.

At every start, the container runs `start.sh`, which does three things:
1. creates any missing tables;
2. seeds the demo users if `SEED_DEMO_DATA=1`;
3. starts gunicorn on `0.0.0.0:$PORT`.

Free services sleep after 15 minutes without traffic. The first request after that can take up to about a minute, which is a good test of your frontend's loading state.

## Configuration

All settings come from environment variables. Locally they are read from `.env` (see `.env.example`).

| Variable | Default | Used for |
|---|---|---|
| `APP_CONFIG` | `development` | Which config class `create_app()` uses when started by the `flask` command: `development`, `testing` or `production`. Docker and Render use `production`. |
| `DATABASE_URL` | SQLite `instance/taskapi.db` in development | The database. Required in production. `docker compose` sets its own Postgres URL (host `db`). |
| `JWT_SECRET` | an insecure placeholder in development | Signs the login tokens. Required in production. |
| `TOKEN_TTL_MINUTES` | `60` | Token lifetime. |
| `CORS_ORIGINS` | `http://localhost:5173` | The frontend origins allowed to call the API from a browser. |
| `SEED_DEMO_DATA` | `0` (`1` in `docker-compose.yml`) | Docker image only: adds the demo users at startup. |
| `PORT` | `8000` | Docker image only: the port gunicorn listens on. Render sets it. |

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use an in-memory SQLite database and need no running server.

## Project layout

```
fe103-reference-api/
  taskapi/
    __init__.py       create_app: config, extensions, blueprints, error handlers, CLI
    config.py         DevelopmentConfig, TestingConfig, ProductionConfig
    extensions.py     db (Flask-SQLAlchemy) and cors (flask-cors)
    models.py         User and Task
    errors.py         the error shape and the JSON error handlers
    security.py       password hashing, JWT tokens, @auth_required
    validation.py     input checks that build the "fields" object
    commands.py       flask init-db and flask seed
    routes/           one blueprint each: health, auth, users, tasks
  tests/              the pytest suite
  start.sh            container start: init-db, seed, gunicorn
  Dockerfile
  docker-compose.yml
  .env.example        every setting, with placeholders
  requirements.txt
  requirements-dev.txt
```

## Troubleshooting

- **`address already in use` on port 8000.** Something else is using that port.
  - Locally: run `flask --app taskapi run --port 8001`.
  - With Docker: change `"8000:8000"` in `docker-compose.yml` to `"8001:8000"`.

  Then use `http://localhost:8001` as your API URL.
- **`env file .env not found` from docker compose.** Copy `.env.example` to `.env` first.
- **Requests to port 5000 on macOS answer 403 and never reach Flask.** That is AirPlay Receiver. Use `--port 8000`.
- **The Vite proxy says `ECONNREFUSED ::1:8000`.** Node looked up `localhost` as the IPv6 address. Use `http://127.0.0.1:8000` as the proxy target.
- **Every request answers `401 invalid_token` right after login.** Check that the header is exactly `Authorization: Bearer <token>`. If it says `Bearer null` or `Bearer undefined`, the frontend read the token before it was saved.
- **`400 invalid_json`.** The request has a body but no `Content-Type: application/json` header, or the body isn't valid JSON.
- **Old tokens stopped working.** Did `JWT_SECRET` change? Every token is signed with it, so changing it logs everyone out. Log in again.
