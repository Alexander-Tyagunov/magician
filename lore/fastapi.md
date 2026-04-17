Common AI mistakes: forgetting `async def` for async route handlers; not using `Depends()` for dependency injection; returning raw dicts instead of Pydantic response models; forgetting `await` on async database calls.
Commands: dev: `uvicorn main:app --reload`, test: `pytest`.
Gotchas: Pydantic v2 uses `model_dump()` not `.dict()`; use `HTTPException` not raw exceptions; background tasks with `BackgroundTasks` avoid blocking the response.
