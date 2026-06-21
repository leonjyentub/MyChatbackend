# MyChatbackend

FastAPI backend for the teaching chat app.

## Local development

```bash
uv run uvicorn main:app --reload
```

Open:

- API root: <http://127.0.0.1:8000/>
- API docs: <http://127.0.0.1:8000/docs>
- Demo seed data: <http://127.0.0.1:8000/dev/seed>

## JWT login, verification, and permissions

This API now uses JWT bearer tokens for protected routes.

### Env vars

- `JWT_SECRET`: signing key for JWT (required in production)
- `JWT_ALGORITHM`: default `HS256`
- `JWT_EXPIRE_MINUTES`: token expiry in minutes, default `60`
- `ADMIN_USERNAMES`: comma-separated admin usernames (for example: `admin,teacher1`)

Example:

```bash
export JWT_SECRET="replace-with-a-long-random-secret"
export JWT_EXPIRE_MINUTES=120
export ADMIN_USERNAMES="alice"
```

### Auth flow

1. Register user:

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"1234","display_name":"Alice"}'
```

1. Login and get token:

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"1234"}'
```

The login response returns:

- `access_token`
- `token_type` (`bearer`)
- `expires_in`
- `role`
- `user`

1. Access protected route with bearer token:

```bash
curl http://127.0.0.1:8000/users/alice001 \
  -H "Authorization: Bearer <access_token>"
```

### Permission rules

- `GET/PUT /users/{user_id}`: only self or admin
- `GET/POST /users/{user_id}/friends`: only self or admin
- `GET /users/{user_id}/chats`: only self or admin
- `GET/POST /chats/{user_id}/{friend_id}/messages`: only self or admin

Unauthenticated requests to protected routes return `401`.
Authenticated users without permission return `403`.

## Deploy to Render

This repo includes `render.yaml`, so Render can read the service settings
automatically.

1. Go to <https://dashboard.render.com/>
2. Click **New** > **Blueprint**
3. Connect the GitHub repo: `leonjyentub/MyChatbackend`
4. Keep the detected `render.yaml` settings and create the service
5. In the service environment variables, set `DATABASE_URL` to your Render
   PostgreSQL internal connection string

If you create a Web Service manually instead, use:

- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/`
- Environment Variable:
  - `DATABASE_URL`: your Render PostgreSQL internal connection string
  - `JWT_SECRET`: a long random value

When `DATABASE_URL` is set, the API stores users, friendships, and messages in
PostgreSQL. Without it, local development still uses the in-memory demo store.

After deployment, test:

- `https://YOUR-SERVICE.onrender.com/`
- `https://YOUR-SERVICE.onrender.com/docs`
- `https://YOUR-SERVICE.onrender.com/dev/seed`
