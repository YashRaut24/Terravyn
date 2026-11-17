import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from server.agents import technical_evaluator
from server.schemas import Rubric


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


class EvaluateAnswerTests(unittest.TestCase):
    def test_sends_question_answer_and_rubric_and_validates_result(self) -> None:
        response = {
            "score": 4,
            "missed_points": ["Did not mention a 404 response."],
            "ideal_answer": "A 404 indicates the requested resource was not found.",
        }
        with patch.object(
            technical_evaluator,
            "generate_response",
            return_value=response,
        ) as generate_response:
            result = technical_evaluator.evaluate_answer(
                "  What does HTTP 404 mean? ",
                "  The resource was not found. ",
                make_rubric(),
            )

        self.assertEqual(result.model_dump(), response)
        prompt, messages = generate_response.call_args.args
        self.assertIn("criterion weights", prompt)
        context = json.loads(messages[0]["content"])
        self.assertEqual(context["question"], "What does HTTP 404 mean?")
        self.assertEqual(context["candidate_answer"], "The resource was not found.")
        self.assertEqual(context["rubric"]["name"], "Backend Intern")
        self.assertEqual(generate_response.call_args.kwargs["output_format"], "json")

    def test_rejects_score_outside_rubric_range(self) -> None:
        response = {
            "score": 6,
            "missed_points": [],
            "ideal_answer": "An answer.",
        }
        with patch.object(
            technical_evaluator,
            "generate_response",
            return_value=response,
        ):
            with self.assertRaisesRegex(ValueError, "within the rubric range"):
                technical_evaluator.evaluate_answer(
                    "Question?", "Answer.", make_rubric()
                )

    def test_rejects_invalid_output_shape(self) -> None:
        response = {
            "score": "4",
            "missed_points": [],
            "ideal_answer": "An answer.",
            "unexpected": True,
        }
        with patch.object(
            technical_evaluator,
            "generate_response",
            return_value=response,
        ):
            with self.assertRaises(ValidationError):
                technical_evaluator.evaluate_answer(
                    "Question?", "Answer.", make_rubric()
                )

    def test_rejects_blank_question_or_answer_before_llm_call(self) -> None:
        with patch.object(technical_evaluator, "generate_response") as generate_response:
            for question, answer in (("  ", "Answer."), ("Question?", "\n")):
                with self.subTest(question=question, answer=answer):
                    with self.assertRaises(ValueError):
                        technical_evaluator.evaluate_answer(
                            question, answer, make_rubric()
                        )

        generate_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
