import json
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.collection import Collection

from . import db
from .agents.coach import CoachReport, generate_coach_report
from .agents.hr_agent import HREvaluation
from .agents.interviewer import InterviewQuestion, ask_question
from .agents.technical_evaluator import TechnicalEvaluation
from .orchestrator import OrchestrationResult, process_answer
from .schemas import Difficulty, Rubric, Session, TranscriptMessage

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
RUBRICS_DIR = Path(__file__).resolve().parent / "rubrics"


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: str = Field(min_length=1)
    difficulty: Difficulty = "medium"
    max_questions: int = Field(default=10, ge=1)
    rubric_name: str = "backend_intern"


class SubmitAnswerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answer: str = Field(min_length=1)


class SessionAnswerResponse(BaseModel):
    id: UUID
    technical_evaluation: TechnicalEvaluation
    hr_evaluation: HREvaluation
    next_question: str | None
    report_ready: bool
    follow_up: bool
    difficulty_raised: bool


class SessionFinishResponse(BaseModel):
    id: UUID
    report: CoachReport


class SessionSummary(BaseModel):
    id: UUID
    role: str
    difficulty: Difficulty
    question_count: int
    max_questions: int
    finished: bool


def get_sessions_collection() -> Collection[dict[str, Any]]:
    return db.db["sessions"]


SessionsCollection = Annotated[
    Collection[dict[str, Any]],
    Depends(get_sessions_collection),
]


def _load_rubric(rubric_name: str) -> Rubric:
    if not rubric_name.isidentifier():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rubric_name must be a rubric identifier",
        )
    rubric_path = RUBRICS_DIR / f"{rubric_name}.json"
    try:
        with rubric_path.open(encoding="utf-8") as rubric_file:
            return Rubric.model_validate(json.load(rubric_file))
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        ) from error
    except (json.JSONDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configured rubric is invalid",
        ) from error


def _load_session(document: dict[str, Any]) -> Session:
    session_fields = Session.model_fields
    data = {
        field: document[field]
        for field in session_fields
        if field in document
    }
    return Session.model_validate(data)


def _persist_state(
    collection: Collection[dict[str, Any]],
    session: Session,
    **updates: Any,
) -> None:
    values = session.model_dump(mode="json")
    values.update(updates)
    result = collection.update_one({"_id": str(session.id)}, {"$set": values})
    if result.matched_count != 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )


@router.post("", response_model=Session, status_code=status.HTTP_201_CREATED)
def create_session(
    request: CreateSessionRequest,
    collection: SessionsCollection,
) -> Session:
    rubric = _load_rubric(request.rubric_name)
    session = Session(
        role=request.role,
        difficulty=request.difficulty,
        max_questions=request.max_questions,
    )
    first_question = ask_question(session, rubric)
    session.transcript.append(
        TranscriptMessage(role="interviewer", content=first_question.question)
    )
    session.asked_topics.append(first_question.topic)
    document = session.model_dump(mode="json")
    document.update(
        {
            "_id": str(session.id),
            "rubric_name": request.rubric_name,
            "finished": False,
            "report": None,
        }
    )
    collection.insert_one(document)
    return session


@router.post(
    "/{session_id}/answer",
    response_model=SessionAnswerResponse,
)
def submit_answer(
    session_id: UUID,
    request: SubmitAnswerRequest,
    collection: SessionsCollection,
) -> SessionAnswerResponse:
    document = collection.find_one({"_id": str(session_id)})
    if document is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if document.get("finished"):
        raise HTTPException(status_code=409, detail="Session is already finished")

    session = _load_session(document)
    rubric = _load_rubric(document["rubric_name"])
    if not session.transcript or session.transcript[-1].role != "interviewer":
        raise HTTPException(
            status_code=409,
            detail="Session has no unanswered interviewer question",
        )
    result: OrchestrationResult = process_answer(
        session,
        session.transcript[-1].content,
        request.answer,
        rubric,
    )
    _persist_state(collection, session)
    return SessionAnswerResponse(
        id=session.id,
        technical_evaluation=result.technical_evaluation,
        hr_evaluation=result.hr_evaluation,
        next_question=result.next_question,
        report_ready=result.report_ready,
        follow_up=result.follow_up,
        difficulty_raised=result.difficulty_raised,
    )


@router.post(
    "/{session_id}/finish",
    response_model=SessionFinishResponse,
)
def finish_session(
    session_id: UUID,
    collection: SessionsCollection,
) -> SessionFinishResponse:
    document = collection.find_one({"_id": str(session_id)})
    if document is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if document.get("report") is not None:
        return SessionFinishResponse(
            id=session_id,
            report=CoachReport.model_validate(document["report"]),
        )

    session = _load_session(document)
    if session.question_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Session must contain at least one answered question",
        )
    report = generate_coach_report(session)
    _persist_state(
        collection,
        session,
        finished=True,
        report=report.model_dump(mode="json"),
    )
    return SessionFinishResponse(id=session.id, report=report)


@router.get("/{session_id}/report", response_model=CoachReport)
def get_session_report(
    session_id: UUID,
    collection: SessionsCollection,
) -> CoachReport:
    document = collection.find_one({"_id": str(session_id)})
    if document is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if document.get("report") is None:
        raise HTTPException(status_code=404, detail="Session report not found")
    return CoachReport.model_validate(document["report"])


@router.get("", response_model=list[SessionSummary])
def list_sessions(collection: SessionsCollection) -> list[SessionSummary]:
    summaries = []
    for document in collection.find():
        session = _load_session(document)
        summaries.append(
            SessionSummary(
                id=session.id,
                role=session.role,
                difficulty=session.difficulty,
                question_count=session.question_count,
                max_questions=session.max_questions,
                finished=bool(document.get("finished", False)),
            )
        )
    return summaries
