import builtins
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from server import interviewer_cli, orchestrator
from server.agents.coach import CoachReport
from server.agents.hr_agent import HREvaluation
from server.agents.interviewer import InterviewQuestion
from server.agents.technical_evaluator import TechnicalEvaluation
from server.schemas import Rubric


def make_rubric() -> Rubric:
    return Rubric(
        name="Backend Intern",
        criteria=[
            {
                "name": "API fundamentals",
                "description": "Understands HTTP and APIs.",
                "weight": 0.5,
            },
            {
                "name": "Testing and code quality",
                "description": "Writes useful tests.",
                "weight": 0.5,
            },
        ],
    )


def make_report() -> CoachReport:
    return CoachReport(
        overall_score=4,
        strengths=["Explains concepts clearly."],
        weaknesses=["Could add more test cases."],
        ideal_answers=[
            {
                "question": "What is an API?",
                "answer": "An API defines how software components communicate.",
            }
        ],
        seven_day_plan=[
            {
                "day": day,
                "focus": f"Practice topic {day}",
                "action": f"Complete exercise {day}.",
            }
            for day in range(1, 8)
        ],
    )


class InterviewerCliTests(unittest.TestCase):
    def test_runs_interview_evaluations_and_final_coach_report(self) -> None:
        initial_question = InterviewQuestion(
            question="What is an API?",
            topic="API fundamentals",
        )
        next_question = InterviewQuestion(
            question="How would you test an endpoint?",
            topic="Testing and code quality",
        )
        technical = TechnicalEvaluation(
            score=3,
            missed_points=["Did not mention error responses."],
            ideal_answer="An API defines a contract between software components.",
        )
        hr = HREvaluation(
            structure_score=4,
            clarity_score=4,
            confidence_score=4,
            feedback="Organize the answer as a short sequence.",
        )
        answers = iter(("An API lets systems communicate.", "Test success and failure."))
        output = StringIO()
        with (
            patch.object(interviewer_cli, "ask_question", return_value=initial_question),
            patch.object(orchestrator, "evaluate_answer", return_value=technical) as technical_eval,
            patch.object(orchestrator, "evaluate_communication", return_value=hr) as hr_eval,
            patch.object(
                orchestrator,
                "ask_question",
                return_value=next_question,
            ) as ask_next,
            patch.object(
                interviewer_cli,
                "generate_coach_report",
                return_value=make_report(),
            ) as generate_report,
            patch.object(builtins, "input", side_effect=lambda _: next(answers)),
            redirect_stdout(output),
        ):
            state = interviewer_cli.run_interview(
                "backend intern",
                "medium",
                make_rubric(),
                max_questions=2,
            )

        self.assertEqual(state.question_count, 2)
        self.assertEqual(
            [(message.role, message.content) for message in state.transcript],
            [
                ("interviewer", "What is an API?"),
                ("candidate", "An API lets systems communicate."),
                ("interviewer", "How would you test an endpoint?"),
                ("candidate", "Test success and failure."),
            ],
        )
        self.assertEqual(
            state.asked_topics,
            ["API fundamentals", "Testing and code quality"],
        )
        self.assertEqual(technical_eval.call_count, 2)
        self.assertEqual(hr_eval.call_count, 2)
        ask_next.assert_called_once_with(
            state,
            make_rubric(),
            follow_up=False,
        )
        generate_report.assert_called_once_with(state)
        self.assertIn("Interview report:", output.getvalue())
        self.assertIn('"overall_score": 4', output.getvalue())


if __name__ == "__main__":
    unittest.main()
