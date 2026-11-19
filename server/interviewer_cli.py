import argparse
import json
from pathlib import Path

from .agents.interviewer import ask_question
from .schemas import Difficulty, Rubric, SharedState, TranscriptMessage


def load_rubric(path: Path) -> Rubric:
    with path.open(encoding="utf-8") as rubric_file:
        return Rubric.model_validate(json.load(rubric_file))


def run_interview(
    role: str,
    difficulty: Difficulty,
    rubric: Rubric,
) -> SharedState:
    state = SharedState(role=role, difficulty=difficulty)
    print("Interviewer-only session. Type /quit to end.")

    while True:
        interview_question = ask_question(state, rubric)
        question = interview_question.question
        if interview_question.topic not in state.asked_topics:
            state.asked_topics.append(interview_question.topic)
        print(f"\nInterviewer: {question}")
        state.transcript.append(
            TranscriptMessage(role="interviewer", content=question)
        )
        state.question_count += 1

        while True:
            answer = input("You: ").strip()
            if answer.casefold() in {"/quit", "quit", "exit"}:
                return state
            if answer:
                break
            print("Please enter an answer or type /quit.")

        state.transcript.append(
            TranscriptMessage(role="candidate", content=answer)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an interactive session with the Interviewer agent."
    )
    parser.add_argument("--role", default="backend intern")
    parser.add_argument(
        "--difficulty",
        choices=("easy", "medium", "hard"),
        default="medium",
    )
    parser.add_argument(
        "--rubric",
        type=Path,
        default=Path(__file__).resolve().parent / "rubrics" / "backend_intern.json",
    )
    args = parser.parse_args()

    try:
        run_interview(args.role, args.difficulty, load_rubric(args.rubric))
    except KeyboardInterrupt:
        print("\nInterview ended.")


if __name__ == "__main__":
    main()
