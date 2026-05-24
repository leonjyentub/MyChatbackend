# MyChatbackend

FastAPI backend for the teaching chat app.

## Local development

```bash
uv run uvicorn main:app --reload
```

Open:

- API root: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs

## Deploy to Render

This repo includes `render.yaml`, so Render can read the service settings
automatically.

1. Go to https://dashboard.render.com/
2. Click **New** > **Blueprint**
3. Connect the GitHub repo: `leonjyentub/MyChatbackend`
4. Keep the detected `render.yaml` settings and create the service

If you create a Web Service manually instead, use:

- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/`

After deployment, test:

- `https://YOUR-SERVICE.onrender.com/`
- `https://YOUR-SERVICE.onrender.com/docs`
