# Backend

```bash
uv sync
uv run python -m ml.download_and_train
uv run uvicorn app.main:app --reload --port 8000
```

Apply `app/schema.sql` in the Supabase SQL editor so reviews persist. Without it, the API uses an in-memory store.
