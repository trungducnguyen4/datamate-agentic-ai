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


class ExecutionTrace(BaseModel):
    id: str
    status: str  # "SUCCESS", "UNANSWERABLE", "ABSTAIN_BUSINESS_RULE", "EXECUTION_ERROR"
    intent: Optional[str] = None
    sql: Optional[str] = None
    params: Optional[List[Any]] = None
    error_phase: Optional[str] = None  # "LOADER", "SCHEMA", "COMPILER", "SQL_EXECUTION", "FORMATTER"
    error_message: Optional[str] = None
    latency_ms: float = 0.0
