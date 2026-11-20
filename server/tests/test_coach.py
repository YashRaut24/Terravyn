import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from server.agents import coach
from server.schemas import SharedState, TranscriptMessage


def make_report() -> dict[str, object]:
    return {
        "overall_score": 4,
        "strengths": ["Explains technical concepts clearly."],
        "weaknesses": ["Could include more detail about testing."],
        "ideal_answers": [
            {
                "question": "How do you test an endpoint?",
                "answer": "Test successful responses, invalid input, and error cases.",
            }
        ],
        "seven_day_plan": [
            {
                "day": day,
                "focus": f"Practice topic {day}",
                "action": f"Complete and review exercise {day}.",
            }
            for day in range(1, 8)
        ],
    }


class GenerateCoachReportTests(unittest.TestCase):
    def test_sends_complete_state_and_validates_report(self) -> None:
        state = SharedState(
            role="backend intern",
            notes="Technical score: 4/5. Practice test design.",
            question_count=2,
            asked_topics=["API fundamentals"],
            transcript=[
                TranscriptMessage(
                    role="interviewer",
                    content="What is an HTTP endpoint?",
                ),
                TranscriptMessage(
                    role="candidate",
                    content="A URL that handles a request.",
                ),
                TranscriptMessage(
                    role="interviewer",
                    content="How do you test one?",
                ),
                TranscriptMessage(
                    role="candidate",
                    content="I test the expected response.",
                ),
            ],
        )
        response = make_report()
        with patch.object(
            coach,
            "generate_response",
            return_value=response,
        ) as generate_response:
            report = coach.generate_coach_report(state)

        self.assertEqual(report.model_dump(), response)
        prompt, messages = generate_response.call_args.args
        self.assertIn("complete interview transcript", prompt)
        context = json.loads(messages[0]["content"])
        self.assertEqual(context["notes"], state.notes)
        self.assertEqual(context["role"], state.role)
        self.assertEqual(
            context["transcript"],
            [message.model_dump() for message in state.transcript],
        )
        self.assertEqual(context["asked_topics"], ["API fundamentals"])
        self.assertEqual(
            generate_response.call_args.kwargs["output_format"],
            "json",
        )

    def test_rejects_score_outside_range_and_missing_report_fields(self) -> None:
        invalid_reports = (
            {**make_report(), "overall_score": 6},
            {key: value for key, value in make_report().items() if key != "weaknesses"},
        )
        for response in invalid_reports:
            with self.subTest(response=response):
                with patch.object(coach, "generate_response", return_value=response):
                    with self.assertRaises(ValidationError):
                        coach.generate_coach_report(SharedState(role="backend intern"))

    def test_rejects_a_plan_that_does_not_cover_exactly_days_one_through_seven(self) -> None:
        response = make_report()
        response["seven_day_plan"] = [
            {
                "day": day,
                "focus": f"Practice topic {day}",
                "action": f"Complete and review exercise {day}.",
            }
            for day in range(1, 7)
        ] + [
            {
                "day": 6,
                "focus": "Duplicate day",
                "action": "Repeat a previous exercise.",
            }
        ]
        with patch.object(
            coach,
            "generate_response",
            return_value=response,
        ):
            with self.assertRaises(ValidationError):
                coach.generate_coach_report(SharedState(role="backend intern"))

    def test_rejects_extra_fields_and_blank_ideal_answers(self) -> None:
        response = make_report()
        response["unexpected"] = True
        with patch.object(
            coach,
            "generate_response",
            return_value=response,
        ):
            with self.assertRaises(ValidationError):
                coach.generate_coach_report(
                    SharedState(role="backend intern")
                )

        response = make_report()
        response["ideal_answers"] = [{"question": "A question?", "answer": "  "}]
        with patch.object(
            coach,
            "generate_response",
            return_value=response,
        ):
            with self.assertRaises(ValidationError):
                coach.generate_coach_report(
                    SharedState(role="backend intern")
                )


if __name__ == "__main__":
    unittest.main()
