import copy
import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from server import db
from server.main import app
from server.routes import get_sessions_collection
from server.orchestrator import OrchestrationResult
from server.agents.coach import CoachReport
from server.agents.hr_agent import HREvaluation
from server.agents.interviewer import InterviewQuestion
from server.agents.technical_evaluator import TechnicalEvaluation
from server.schemas import TranscriptMessage


class FakeUpdateResult:
    def __init__(self, matched_count: int) -> None:
        self.matched_count = matched_count


class FakeSessionsCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}

    def insert_one(self, document: dict[str, object]) -> None:
        self.documents[str(document["_id"])] = copy.deepcopy(document)

    def find_one(self, query: dict[str, object]) -> dict[str, object] | None:
        document = self.documents.get(str(query["_id"]))
        return copy.deepcopy(document) if document is not None else None

    def find(self) -> list[dict[str, object]]:
        return [copy.deepcopy(document) for document in self.documents.values()]

    def update_one(
        self,
        query: dict[str, object],
        update: dict[str, dict[str, object]],
    ) -> FakeUpdateResult:
        document = self.documents.get(str(query["_id"]))
        if document is None:
            return FakeUpdateResult(0)
        document.update(copy.deepcopy(update["$set"]))
        return FakeUpdateResult(1)


def make_report() -> CoachReport:
    return CoachReport(
        overall_score=4,
        strengths=["Clear explanations."],
        weaknesses=["Add more detail about testing."],
        ideal_answers=[
            {
                "question": "What is an API?",
                "answer": "An API defines communication between components.",
            }
        ],
        seven_day_plan=[
            {
                "day": day,
                "focus": f"Topic {day}",
                "action": f"Practice exercise {day}.",
            }
            for day in range(1, 8)
        ],
    )


class SessionRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collection = FakeSessionsCollection()
        app.dependency_overrides[get_sessions_collection] = lambda: self.collection
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    @classmethod
    def tearDownClass(cls) -> None:
        db.client.close()

    def test_create_answer_finish_get_report_and_list(self) -> None:
        with patch(
            "server.routes.ask_question",
            return_value=InterviewQuestion(
                question="What is an API?",
                topic="API and HTTP fundamentals",
            ),
        ) as ask_question:
            create_response = self.client.post(
                "/api/sessions",
                json={
                    "role": "backend intern",
                    "max_questions": 2,
                },
            )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        session_id = created["id"]
        self.assertEqual(created["transcript"][0]["content"], "What is an API?")
        self.assertEqual(created["asked_topics"], ["API and HTTP fundamentals"])
        ask_question.assert_called_once()

        def fake_process_answer(
            state: object,
            question: str,
            answer: str,
            rubric: object,
        ) -> OrchestrationResult:
            state.transcript.append(
                TranscriptMessage(role="candidate", content=answer)
            )
            state.question_count += 1
            if state.question_count == 1:
                state.transcript.append(
                    TranscriptMessage(
                        role="interviewer",
                        content="How would you test an endpoint?",
                    )
                )
                state.asked_topics.append("Testing and code quality")
            return OrchestrationResult(
                technical_evaluation=TechnicalEvaluation(
                    score=4,
                    missed_points=[],
                    ideal_answer="An API defines communication between components.",
                ),
                hr_evaluation=HREvaluation(
                    structure_score=4,
                    clarity_score=4,
                    confidence_score=4,
                    feedback="Well structured.",
                ),
                next_question=(
                    "How would you test an endpoint?"
                    if state.question_count == 1
                    else None
                ),
                report_ready=state.question_count == state.max_questions,
                follow_up=False,
                difficulty_raised=False,
            )

        with patch(
            "server.routes.process_answer",
            side_effect=fake_process_answer,
        ):
            first_answer = self.client.post(
                f"/api/sessions/{session_id}/answer",
                json={"answer": "An API connects software components."},
            )
            self.assertEqual(first_answer.status_code, 200, first_answer.text)
            self.assertEqual(
                first_answer.json()["next_question"],
                "How would you test an endpoint?",
            )
            second_answer = self.client.post(
                f"/api/sessions/{session_id}/answer",
                json={"answer": "Test successful and failing cases."},
            )
        self.assertEqual(second_answer.status_code, 200, second_answer.text)
        self.assertTrue(second_answer.json()["report_ready"])
        self.assertIsNone(second_answer.json()["next_question"])

        report = make_report()
        with patch("server.routes.generate_coach_report", return_value=report) as coach:
            finish_response = self.client.post(
                f"/api/sessions/{session_id}/finish"
            )
        self.assertEqual(finish_response.status_code, 200, finish_response.text)
        self.assertEqual(finish_response.json()["report"]["overall_score"], 4)
        coach.assert_called_once()

        report_response = self.client.get(f"/api/sessions/{session_id}/report")
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["seven_day_plan"][6]["day"], 7)

        list_response = self.client.get("/api/sessions")
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(len(list_response.json()), 1)
        summary = list_response.json()[0]
        self.assertEqual(summary["id"], session_id)
        self.assertEqual(summary["question_count"], 2)
        self.assertTrue(summary["finished"])

        with patch("server.routes.generate_coach_report") as coach:
            repeated_finish = self.client.post(
                f"/api/sessions/{session_id}/finish"
            )
        self.assertEqual(repeated_finish.status_code, 200)
        coach.assert_not_called()

    def test_unknown_session_and_unavailable_report_return_404(self) -> None:
        missing_id = UUID("00000000-0000-0000-0000-000000000001")
        self.assertEqual(
            self.client.post(
                f"/api/sessions/{missing_id}/answer",
                json={"answer": "Answer"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(f"/api/sessions/{missing_id}/finish").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/sessions/{missing_id}/report").status_code,
            404,
        )

    def test_rejects_unknown_rubric(self) -> None:
        response = self.client.post(
            "/api/sessions",
            json={"role": "backend intern", "rubric_name": "missing"},
        )
        self.assertEqual(response.status_code, 404)

    def test_rejects_blank_role_and_answer(self) -> None:
        create_response = self.client.post(
            "/api/sessions",
            json={"role": "   "},
        )
        self.assertEqual(create_response.status_code, 422)

        with patch(
            "server.routes.ask_question",
            return_value=InterviewQuestion(
                question="What is an API?",
                topic="API and HTTP fundamentals",
            ),
        ):
            created = self.client.post(
                "/api/sessions",
                json={"role": "backend intern"},
            )
        session_id = created.json()["id"]
        answer_response = self.client.post(
            f"/api/sessions/{session_id}/answer",
            json={"answer": "  "},
        )
        self.assertEqual(answer_response.status_code, 422)

    def test_rejects_answer_after_max_questions(self) -> None:
        with patch(
            "server.routes.ask_question",
            return_value=InterviewQuestion(
                question="What is an API?",
                topic="API and HTTP fundamentals",
            ),
        ):
            response = self.client.post(
                "/api/sessions",
                json={"role": "backend intern", "max_questions": 1},
            )
        self.assertEqual(response.status_code, 201, response.text)
        session_id = response.json()["id"]

        def finish_last_answer(
            state: object,
            question: str,
            answer: str,
            rubric: object,
        ) -> OrchestrationResult:
            state.transcript.append(
                TranscriptMessage(role="candidate", content=answer)
            )
            state.question_count += 1
            return OrchestrationResult(
                technical_evaluation=TechnicalEvaluation(
                    score=3,
                    missed_points=[],
                    ideal_answer="An API is a software interface.",
                ),
                hr_evaluation=HREvaluation(
                    structure_score=3,
                    clarity_score=3,
                    confidence_score=3,
                    feedback="Answer clearly.",
                ),
                next_question=None,
                report_ready=True,
                follow_up=False,
                difficulty_raised=False,
            )

        with patch(
            "server.routes.process_answer",
            side_effect=finish_last_answer,
        ):
            answer_response = self.client.post(
                f"/api/sessions/{session_id}/answer",
                json={"answer": "An API is an interface."},
            )
        self.assertEqual(answer_response.status_code, 200, answer_response.text)
        self.assertTrue(answer_response.json()["report_ready"])
        self.assertEqual(
            self.client.post(
                f"/api/sessions/{session_id}/answer",
                json={"answer": "Another answer."},
            ).status_code,
            409,
        )


if __name__ == "__main__":
    unittest.main()
