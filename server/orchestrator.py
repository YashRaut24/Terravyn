from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .agents.hr_agent import HREvaluation, evaluate_communication
from .agents.interviewer import ask_question
from .agents.technical_evaluator import TechnicalEvaluation, evaluate_answer
from .schemas import Rubric, SharedState, TranscriptMessage


@dataclass(frozen=True)
class OrchestrationResult:
    technical_evaluation: TechnicalEvaluation
    hr_evaluation: HREvaluation
    next_question: str


def process_answer(
    state: SharedState,
    question: str,
    answer: str,
    rubric: Rubric,
) -> OrchestrationResult:
    question = question.strip()
    answer = answer.strip()
    if not question:
        raise ValueError("question must not be empty")
    if not answer:
        raise ValueError("answer must not be empty")
    if not state.transcript:
        raise ValueError("transcript must end with the current interviewer question")

    last_message = state.transcript[-1]
    if last_message.role != "interviewer" or last_message.content.strip() != question:
        raise ValueError("transcript must end with the current interviewer question")

    state.transcript.append(TranscriptMessage(role="candidate", content=answer))

    with ThreadPoolExecutor(max_workers=2) as executor:
        technical_future = executor.submit(evaluate_answer, question, answer, rubric)
        hr_future = executor.submit(evaluate_communication, question, answer)
        technical_evaluation = technical_future.result()
        hr_evaluation = hr_future.result()

    missed_points = (
        "; ".join(technical_evaluation.missed_points)
        if technical_evaluation.missed_points
        else "none identified"
    )
    evaluation_notes = (
        f"Technical evaluation: {technical_evaluation.score}/"
        f"{rubric.max_score}; missed points: {missed_points}.\n"
        "Communication evaluation: "
        f"structure {hr_evaluation.structure_score}/5, "
        f"clarity {hr_evaluation.clarity_score}/5, "
        f"confidence {hr_evaluation.confidence_score}/5; "
        f"feedback: {hr_evaluation.feedback}"
    )
    state.notes = "\n".join(
        note for note in (state.notes.strip(), evaluation_notes) if note
    )

    next_question = ask_question(state)
    state.transcript.append(
        TranscriptMessage(role="interviewer", content=next_question)
    )
    state.question_count += 1

    return OrchestrationResult(
        technical_evaluation=technical_evaluation,
        hr_evaluation=hr_evaluation,
        next_question=next_question,
    )
