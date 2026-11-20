import argparse
import json
from pathlib import Path

from .agents.coach import CoachReport, generate_coach_report
from .agents.interviewer import InterviewQuestion, ask_question
from .orchestrator import process_answer
from .schemas import Difficulty, Rubric, SharedState, TranscriptMessage


def load_rubric(path: Path) -> Rubric:
    with path.open(encoding="utf-8") as rubric_file:
        return Rubric.model_validate(json.load(rubric_file))


def run_interview(
    role: str,
    difficulty: Difficulty,
    rubric: Rubric,
    max_questions: int = 10,
) -> SharedState:
    state = SharedState(
        role=role,
        difficulty=difficulty,
        max_questions=max_questions,
    )
    print("Interview session. Type /quit to end.")

    interview_question = ask_question(state, rubric)
    _record_question(state, interview_question)

    while True:
        question = state.transcript[-1].content
        print(f"\nInterviewer: {question}")

        while True:
            answer = input("You: ").strip()
            if answer.casefold() in {"/quit", "quit", "exit"}:
                return state
            if answer:
                break
            print("Please enter an answer or type /quit.")

        result = process_answer(state, question, answer, rubric)
        print(
            "\nEvaluation:"
            f"\n  Technical score: {result.technical_evaluation.score}/"
            f"{rubric.max_score}"
            f"\n  Communication: structure "
            f"{result.hr_evaluation.structure_score}/5, clarity "
            f"{result.hr_evaluation.clarity_score}/5, confidence "
            f"{result.hr_evaluation.confidence_score}/5"
        )
        if result.report_ready:
            report = generate_coach_report(state)
            _print_report(report)
            return state

        if result.next_question is None:
            raise RuntimeError("The interview ended without a report or next question")


def _record_question(
    state: SharedState,
    interview_question: InterviewQuestion,
) -> None:
    if interview_question.topic not in state.asked_topics:
        state.asked_topics.append(interview_question.topic)
    state.transcript.append(
        TranscriptMessage(
            role="interviewer",
            content=interview_question.question,
        )
    )


def _print_report(report: CoachReport) -> None:
    print("\nInterview report:")
    print(report.model_dump_json(indent=2))


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
    parser.add_argument("--max-questions", type=int, default=10)
    args = parser.parse_args()

    try:
        run_interview(
            args.role,
            args.difficulty,
            load_rubric(args.rubric),
            max_questions=args.max_questions,
        )
    except KeyboardInterrupt:
        print("\nInterview ended.")


if __name__ == "__main__":
    main()
