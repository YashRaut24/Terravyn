import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title=os.getenv("APP_NAME", "Terravyn API"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
