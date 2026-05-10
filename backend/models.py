from pydantic import BaseModel
from typing import Optional


class SessionConfig(BaseModel):
    subject_id: str
    topic_id: Optional[str] = None
    subtopic_id: Optional[str] = None
    session_type: str = "diagnostic"  # diagnostic | adaptive | validation
    mode: str = "fixed_set"           # fixed_set | time_boxed
    num_questions: int = 10
    time_minutes: Optional[int] = None
    difficulty: str = "mixed"


class AnswerSubmit(BaseModel):
    session_id: str
    question_hash: str
    question_text: str
    options: dict
    correct_answer: str
    user_answer: Optional[str] = None
    is_correct: bool
    time_taken_sec: int
    skipped: bool = False
    subject_id: str
    topic_id: Optional[str] = None
    subtopic_id: Optional[str] = None


class AttestationRequest(BaseModel):
    subject_id: str
    claimed_label: str  # strong | very_strong | expert


class SyncRequest(BaseModel):
    available_hours: float = 8.0
