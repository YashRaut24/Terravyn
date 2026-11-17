import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from server.agents import hr_agent


class EvaluateCommunicationTests(unittest.TestCase):
    def test_sends_question_and_answer_and_validates_evaluation(self) -> None:
        response = {
            "structure_score": 4,
            "clarity_score": 5,
            "confidence_score": 3,
            "feedback": "Use a brief summary before adding details.",
        }
        with patch.object(
            hr_agent,
            "generate_response",
            return_value=response,
        ) as generate_response:
            result = hr_agent.evaluate_communication(
                "  Tell me about a challenge. ",
                "  I identified the issue, then fixed it. ",
            )

        self.assertEqual(result.model_dump(), response)
        prompt, messages = generate_response.call_args.args
        self.assertIn("structure", prompt)
        self.assertIn("clarity", prompt)
        self.assertIn("confidence", prompt)
        context = json.loads(messages[0]["content"])
        self.assertEqual(context["question"], "Tell me about a challenge.")
        self.assertEqual(
            context["candidate_answer"],
            "I identified the issue, then fixed it.",
        )
        self.assertEqual(
            generate_response.call_args.kwargs["output_format"],
            "json",
        )

    def test_rejects_scores_outside_range_and_non_integer_scores(self) -> None:
        invalid_responses = (
            {
                "structure_score": 0,
                "clarity_score": 3,
                "confidence_score": 3,
                "feedback": "Feedback.",
            },
            {
                "structure_score": "4",
                "clarity_score": 3,
                "confidence_score": 3,
                "feedback": "Feedback.",
            },
        )
        for response in invalid_responses:
            with self.subTest(response=response):
                with patch.object(
                    hr_agent,
                    "generate_response",
                    return_value=response,
                ):
                    with self.assertRaises(ValidationError):
                        hr_agent.evaluate_communication("Question?", "Answer.")

    def test_rejects_extra_fields_and_blank_feedback(self) -> None:
        valid_scores = {
            "structure_score": 4,
            "clarity_score": 4,
            "confidence_score": 4,
        }
        for response in (
            {**valid_scores, "feedback": " ", "unexpected": True},
            {**valid_scores, "feedback": "  "},
        ):
            with self.subTest(response=response):
                with patch.object(
                    hr_agent,
                    "generate_response",
                    return_value=response,
                ):
                    with self.assertRaises(ValidationError):
                        hr_agent.evaluate_communication("Question?", "Answer.")

    def test_rejects_blank_question_or_answer_without_calling_llm(self) -> None:
        with patch.object(hr_agent, "generate_response") as generate_response:
            for question, answer in ((" ", "Answer."), ("Question?", "\n")):
                with self.subTest(question=question, answer=answer):
                    with self.assertRaises(ValueError):
                        hr_agent.evaluate_communication(question, answer)

        generate_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
