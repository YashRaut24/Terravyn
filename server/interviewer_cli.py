import argparse

from .agents.interviewer import ask_question
from .schemas import Difficulty, SharedState, TranscriptMessage


def run_interview(role: str, difficulty: Difficulty) -> SharedState:
    state = SharedState(role=role, difficulty=difficulty)
    print("Interviewer-only session. Type /quit to end.")

    while True:
        question = ask_question(state)
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
    args = parser.parse_args()

    try:
        run_interview(args.role, args.difficulty)
    except KeyboardInterrupt:
        print("\nInterview ended.")


if __name__ == "__main__":
    main()
