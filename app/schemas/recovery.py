from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    token: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class PasswordResetResponse(BaseModel):
    message: str


class RecoveryQuestionSetup(BaseModel):
    user_id: str
    recovery_question_one: str
    recovery_question_two: str
    recovery_answer_one: str
    recovery_answer_two: str


class RecoveryQuestionUpdate(BaseModel):
    recovery_question_one: Optional[str] = None
    recovery_question_two: Optional[str] = None
    recovery_answer_one: Optional[str] = None
    recovery_answer_two: Optional[str] = None


class RecoveryQuestionResponse(BaseModel):
    user_id: str
    recovery_question_one: Optional[str] = None
    recovery_question_two: Optional[str] = None
