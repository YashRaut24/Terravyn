# Terravyn

Terravyn helps teams evaluate and compare product launch opportunities across regions with source-grounded market research and explainable scoring.

## Server

Copy `.env.example` to `.env` and adjust the values as needed. MongoDB defaults to `mongodb://localhost:27017` and the `terravyn` database; set `MONGODB_URI` and `MONGODB_DATABASE` to change them. Set `OPENAI_API_KEY` to enable LLM requests and optionally change `OPENAI_MODEL`. From the repository root, start the API with:

```powershell
server\venv\Scripts\python.exe -m uvicorn main:app --app-dir server --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

To run a full interactive interview in the terminal, configure `OPENAI_API_KEY` in `.env`, then run:

```powershell
server\venv\Scripts\python.exe -m server.interviewer_cli --role "backend intern" --difficulty medium --max-questions 10
```

The terminal flow asks questions, evaluates each answer with the technical and HR agents, and prints the Coach report at the question limit. Type `/quit` to end early. Use `--rubric` to choose another rubric JSON file.

The answer workflow asks a focused follow-up when the technical score is 2 or lower. A technical score of 4 or higher together with an average HR score of 4 or higher raises interview difficulty by one level. Sessions default to 10 answered questions; reaching the limit returns a report-ready result without another question.

The session API provides `POST /api/sessions` to create a session, `POST /api/sessions/{id}/answer` to submit an answer, `POST /api/sessions/{id}/finish` to generate and save the Coach report, `GET /api/sessions/{id}/report` to retrieve it, and `GET /api/sessions` to list sessions. Session creation accepts a role, difficulty, question limit, and rubric name (`backend_intern` by default).
