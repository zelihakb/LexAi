from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class FindRequest(BaseModel):
    query: str = ""
    filters: Optional[Dict[str, str]] = None


class ConfidenceSchema(BaseModel):
    status: str
    reason: str


class DecisionPayloadSchema(BaseModel):
    court: str = ""
    case_no: str = ""
    decision_no: str = ""
    decision_date: str = ""
    folder: str = ""
    text: str = ""


class DecisionItemSchema(BaseModel):
    final_score: float
    payload: DecisionPayloadSchema


class AskResponse(BaseModel):
    mode: str
    final_answer: str
    confidence: ConfidenceSchema
    final_direction: str
    final_items: List[DecisionItemSchema]


class FindResponse(BaseModel):
    mode: str
    query: str
    filters: Dict[str, str]
    final_items: List[DecisionItemSchema]