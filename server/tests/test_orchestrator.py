import threading
import unittest
from unittest.mock import patch

from server import orchestrator
from server.agents.hr_agent import HREvaluation
from server.agents.technical_evaluator import TechnicalEvaluation
from server.schemas import Rubric, SharedState, TranscriptMessage


def make_rubric() -> Rubric:
    return Rubric(
        name="Backend Intern",
        min_score=1,
        max_score=5,
        criteria=[
            {
                "name": "API fundamentals",
                "description": "Understands HTTP and APIs.",
                "weight": 1.0,
            }
        ],
    )


def make_state() -> SharedState:
    return SharedState(
        role="backend intern",
        notes="Existing interview context.",
        transcript=[
            TranscriptMessage(
                role="interviewer",
                content="What does HTTP 404 mean?",
            )
        ],
    )


class ProcessAnswerTests(unittest.TestCase):
    def test_runs_evaluators_in_parallel_saves_notes_then_asks_next_question(self) -> None:
        state = make_state()
        rubric = make_rubric()
        parallel_barrier = threading.Barrier(2)
        evaluations_finished: set[str] = set()
        technical = TechnicalEvaluation(
            score=4,
            missed_points=["Did not mention resource routing."],
            ideal_answer="A 404 means the requested resource was not found.",
        )
        hr = HREvaluation(
            structure_score=4,
            clarity_score=5,
            confidence_score=3,
            feedback="State the conclusion before explaining it.",
        )

        def evaluate_technical(*args: object) -> TechnicalEvaluation:
            parallel_barrier.wait(timeout=5)
            evaluations_finished.add("technical")
            return technical

        def evaluate_hr(*args: object) -> HREvaluation:
            parallel_barrier.wait(timeout=5)
            evaluations_finished.add("hr")
            return hr

        def ask_next_question(
            updated_state: SharedState,
            *,
            follow_up: bool,
        ) -> str:
            self.assertFalse(follow_up)
            self.assertEqual(evaluations_finished, {"technical", "hr"})
            self.assertIn("Existing interview context.", updated_state.notes)
            self.assertIn("resource routing", updated_state.notes)
            self.assertIn("confidence 3/5", updated_state.notes)
            self.assertEqual(updated_state.transcript[-1].role, "candidate")
            self.assertEqual(
                updated_state.transcript[-1].content,
                "The resource was not found.",
            )
            return "How would you test this endpoint?"

        with (
            patch.object(
                orchestrator,
                "evaluate_answer",
                side_effect=evaluate_technical,
            ),
            patch.object(
                orchestrator,
                "evaluate_communication",
                side_effect=evaluate_hr,
            ),
            patch.object(
                orchestrator,
                "ask_question",
                side_effect=ask_next_question,
            ) as ask_question,
        ):
            result = orchestrator.process_answer(
                state,
                " What does HTTP 404 mean? ",
                " The resource was not found. ",
                rubric,
            )

        self.assertIs(result.technical_evaluation, technical)
        self.assertIs(result.hr_evaluation, hr)
        self.assertEqual(result.next_question, "How would you test this endpoint?")
        self.assertEqual(state.question_count, 1)
        self.assertEqual(
            [(message.role, message.content) for message in state.transcript],
            [
                ("interviewer", "What does HTTP 404 mean?"),
                ("candidate", "The resource was not found."),
                ("interviewer", "How would you test this endpoint?"),
            ],
        )
        ask_question.assert_called_once_with(state, follow_up=False)

    def test_weak_technical_score_routes_to_follow_up(self) -> None:
        state = make_state()
        technical = TechnicalEvaluation(
            score=2,
            missed_points=["Did not explain status codes."],
            ideal_answer="A 404 indicates the resource was not found.",
        )
        hr = HREvaluation(
            structure_score=5,
            clarity_score=5,
            confidence_score=5,
            feedback="Clear answer.",
        )
        with (
            patch.object(orchestrator, "evaluate_answer", return_value=technical),
            patch.object(orchestrator, "evaluate_communication", return_value=hr),
            patch.object(
                orchestrator,
                "ask_question",
                return_value="Can you explain a 404 response?",
            ) as ask_question,
        ):
            result = orchestrator.process_answer(
                state,
                "What does HTTP 404 mean?",
                "I am not sure.",
                make_rubric(),
            )

        self.assertTrue(result.follow_up)
        self.assertFalse(result.difficulty_raised)
        self.assertEqual(state.difficulty, "medium")
        ask_question.assert_called_once_with(state, follow_up=True)

    def test_two_strong_evaluations_raise_difficulty_one_level(self) -> None:
        state = make_state()
        state.difficulty = "easy"
        technical = TechnicalEvaluation(
            score=4,
            missed_points=[],
            ideal_answer="A 404 indicates the resource was not found.",
        )
        hr = HREvaluation(
            structure_score=4,
            clarity_score=5,
            confidence_score=4,
            feedback="Well explained.",
        )
        with (
            patch.object(orchestrator, "evaluate_answer", return_value=technical),
            patch.object(orchestrator, "evaluate_communication", return_value=hr),
            patch.object(orchestrator, "ask_question", return_value="Next?"),
        ):
            result = orchestrator.process_answer(
                state,
                "What does HTTP 404 mean?",
                "The resource was not found.",
                make_rubric(),
            )

        self.assertTrue(result.difficulty_raised)
        self.assertFalse(result.follow_up)
        self.assertEqual(state.difficulty, "medium")

    def test_question_limit_returns_report_ready_without_next_question(self) -> None:
        state = make_state()
        state.max_questions = 1
        technical = TechnicalEvaluation(
            score=4,
            missed_points=[],
            ideal_answer="A 404 indicates the resource was not found.",
        )
        hr = HREvaluation(
            structure_score=4,
            clarity_score=4,
            confidence_score=4,
            feedback="Clear answer.",
        )
        with (
            patch.object(orchestrator, "evaluate_answer", return_value=technical),
            patch.object(orchestrator, "evaluate_communication", return_value=hr),
            patch.object(orchestrator, "ask_question") as ask_question,
        ):
            result = orchestrator.process_answer(
                state,
                "What does HTTP 404 mean?",
                "The resource was not found.",
                make_rubric(),
            )

        self.assertTrue(result.report_ready)
        self.assertIsNone(result.next_question)
        self.assertEqual(state.question_count, 1)
        ask_question.assert_not_called()

    def test_rejects_state_not_ending_with_current_question(self) -> None:
        state = make_state()
        with (
            patch.object(orchestrator, "evaluate_answer") as evaluate_technical,
            patch.object(orchestrator, "evaluate_communication") as evaluate_hr,
            patch.object(orchestrator, "ask_question") as ask_question,
        ):
            with self.assertRaisesRegex(ValueError, "current interviewer question"):
                orchestrator.process_answer(
                    state, "A different question?", "Answer.", make_rubric()
                )

        evaluate_technical.assert_not_called()
        evaluate_hr.assert_not_called()
        ask_question.assert_not_called()

    def test_evaluator_failure_does_not_save_notes_or_ask_next_question(self) -> None:
        state = make_state()
        with (
            patch.object(
                orchestrator,
                "evaluate_answer",
                side_effect=RuntimeError("evaluation failed"),
            ),
            patch.object(
                orchestrator,
                "evaluate_communication",
                return_value=HREvaluation(
                    structure_score=3,
                    clarity_score=3,
                    confidence_score=3,
                    feedback="Answer the question directly.",
                ),
            ),
            patch.object(orchestrator, "ask_question") as ask_question,
        ):
            with self.assertRaisesRegex(RuntimeError, "evaluation failed"):
                orchestrator.process_answer(
                    state,
                    "What does HTTP 404 mean?",
                    "The resource was not found.",
                    make_rubric(),
                )

        self.assertEqual(state.notes, "Existing interview context.")
        self.assertEqual(state.transcript[-1].role, "candidate")
        self.assertEqual(state.question_count, 0)
        ask_question.assert_not_called()


if __name__ == "__main__":
    unittest.main()
