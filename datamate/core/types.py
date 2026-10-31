from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class AnswerType(str, Enum):
    NUMBER = "number"
    PERCENT = "percent"
    STRING = "string"
    DATE = "date"
    BOOLEAN = "boolean"
    LIST = "list"
    TABLE = "table"
    UNANSWERABLE = "unanswerable"
    ABSTAIN = "abstain"


class TableAnswer(BaseModel):
    columns: List[str]
    rows: List[List[Any]]


class QuestionItem(BaseModel):
    id: str
    business_id: str
    question: str
    as_of_date: str = Field(description="Date anchor YYYY-MM-DD")


class SubmissionItem(BaseModel):
    id: str
    type: AnswerType
    answer: Optional[Union[int, float, str, bool, List[Any], Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for submission.jsonl according to contest format."""
        if self.type in (AnswerType.UNANSWERABLE, AnswerType.ABSTAIN):
            # For unanswerable and abstain, answer field is omitted or null
            return {"id": self.id, "type": self.type.value}
        return {
            "id": self.id,
            "type": self.type.value,
            "answer": self.answer,
        }


class EvaluationResult(str, Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    ABSTAIN = "abstain"
