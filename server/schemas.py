from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

Difficulty = Literal["easy", "medium", "hard"]


class TranscriptMessage(BaseModel):
    role: str = Field(min_length=1)
    content: str


class SharedState(BaseModel):
    role: str = Field(min_length=1)
    transcript: list[TranscriptMessage] = Field(default_factory=list)
    asked_topics: list[str] = Field(default_factory=list)
    notes: str = ""
    difficulty: Difficulty = "medium"
    question_count: int = Field(default=0, ge=0)
    max_questions: int = Field(default=10, ge=1)


class Session(SharedState):
    id: UUID = Field(default_factory=uuid4)


class RubricCriterion(BaseModel):
    name: str = Field(min_length=1)
    description: str
    weight: float = Field(ge=0, allow_inf_nan=False)


class Rubric(BaseModel):
    name: str = Field(min_length=1)
    criteria: list[RubricCriterion] = Field(min_length=1)
    min_score: int = Field(default=1, ge=1)
    max_score: int = Field(default=5, ge=2)

    @model_validator(mode="after")
    def validate_score_range(self) -> Self:
        if self.max_score <= self.min_score:
            raise ValueError("max_score must be greater than min_score")
        return self
