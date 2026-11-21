import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from .routes import router as sessions_router

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title=os.getenv("APP_NAME", "Terravyn API"))
app.include_router(sessions_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
