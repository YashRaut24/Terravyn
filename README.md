# Terravyn

Terravyn helps teams evaluate and compare product launch opportunities across regions with source-grounded market research and explainable scoring.

## Server

Copy `.env.example` to `.env` and adjust the values as needed. MongoDB defaults to `mongodb://localhost:27017` and the `terravyn` database; set `MONGODB_URI` and `MONGODB_DATABASE` to change them. From the repository root, start the API with:

```powershell
server\venv\Scripts\python.exe -m uvicorn main:app --app-dir server --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.
