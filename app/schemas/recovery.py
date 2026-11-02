from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    token: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_within_bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value

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
