# Terravyn

Terravyn helps teams evaluate and compare product launch opportunities across regions with source-grounded market research and explainable scoring.

## Server

Copy `.env.example` to `.env` and adjust the values as needed. MongoDB defaults to `mongodb://localhost:27017` and the `terravyn` database; set `MONGODB_URI` and `MONGODB_DATABASE` to change them. Set `OPENAI_API_KEY` to enable LLM requests and optionally change `OPENAI_MODEL`. From the repository root, start the API with:

```powershell
server\venv\Scripts\python.exe -m uvicorn main:app --app-dir server --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

To run an interactive Interviewer-only session in the terminal, configure `OPENAI_API_KEY` in `.env`, then run:

```powershell
server\venv\Scripts\python.exe -m server.interviewer_cli --role "backend intern" --difficulty medium
```

Type `/quit` to end the session.

The answer workflow asks a focused follow-up when the technical score is 2 or lower. A technical score of 4 or higher together with an average HR score of 4 or higher raises interview difficulty by one level. Sessions default to 10 answered questions; reaching the limit returns a report-ready result without another question.
