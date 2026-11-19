import json
import unittest
from unittest.mock import patch

from server.agents import interviewer
from server.schemas import Rubric, SharedState


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
                "description": "Writes useful tests and maintainable code.",
                "weight": 0.5,
            },
        ],
    )


class AskQuestionTests(unittest.TestCase):
    def test_sends_topics_and_validates_selected_rubric_topic(self) -> None:
        state = SharedState(
            role="backend intern",
            asked_topics=["API fundamentals"],
        )
        response = {
            "question": "How would you test this endpoint?",
            "topic": "Testing and code quality",
        }
        with patch.object(
            interviewer,
            "generate_response",
            return_value=response,
        ) as generate_response:
            question = interviewer.ask_question(state, make_rubric())

        self.assertEqual(question.question, response["question"])
        self.assertEqual(question.topic, response["topic"])
        prompt, messages = generate_response.call_args.args
        self.assertIn("Do not select a topic already listed", prompt)
        context = json.loads(messages[0]["content"])
        self.assertEqual(context["asked_topics"], ["API fundamentals"])
        self.assertEqual(
            generate_response.call_args.kwargs["output_format"],
            "json",
        )

    def test_rejects_repeated_topic_unless_it_is_a_follow_up(self) -> None:
        state = SharedState(
            role="backend intern",
            asked_topics=["API fundamentals"],
        )
        response = {
            "question": "Can you explain the status code?",
            "topic": "API fundamentals",
        }
        with patch.object(
            interviewer,
            "generate_response",
            return_value=response,
        ):
            with self.assertRaisesRegex(ValueError, "already asked"):
                interviewer.ask_question(state, make_rubric())

            follow_up = interviewer.ask_question(
                state,
                make_rubric(),
                follow_up=True,
            )

        self.assertEqual(follow_up.topic, "API fundamentals")

    def test_rejects_topic_not_in_rubric(self) -> None:
        with patch.object(
            interviewer,
            "generate_response",
            return_value={"question": "Next?", "topic": "Unlisted topic"},
        ):
            with self.assertRaisesRegex(ValueError, "match a rubric criterion"):
                interviewer.ask_question(SharedState(role="backend intern"), make_rubric())

    def test_rejects_malformed_question_response(self) -> None:
        with patch.object(
            interviewer,
            "generate_response",
            return_value={"question": "Next?", "topic": "Testing and code quality", "extra": 1},
        ):
            with self.assertRaises(ValueError):
                interviewer.ask_question(SharedState(role="backend intern"), make_rubric())


if __name__ == "__main__":
    unittest.main()
