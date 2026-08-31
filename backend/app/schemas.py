from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field


# ===================== USER & AUTH SCHEMAS =====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


# ===================== DOCUMENT SCHEMAS =====================

class DocumentOut(BaseModel):
    id: int
    filename: str
    file_size: int
    total_pages: int
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    message: str
    documents: List[DocumentOut]


# ===================== CHAT & RAG SCHEMAS =====================

class CitationSource(BaseModel):
    doc_id: int
    filename: str
    page: int
    chunk_text: str
    score: Optional[float] = None


class ChatQueryRequest(BaseModel):
    question: str
    document_ids: Optional[List[int]] = None  # None means search across all user's documents


class ChatMessageOut(BaseModel):
    id: int
    sender: str
    content: str
    sources: Optional[List[CitationSource]] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Study Session"


class ChatSessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageOut] = []

    class Config:
        from_attributes = True


class ChatSessionSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


# ===================== QUIZ SCHEMAS =====================

class QuizGenerateRequest(BaseModel):
    document_id: Optional[int] = None # None means generate from all user documents
    difficulty: str = Field("Medium", pattern="^(Easy|Medium|Hard)$")
    total_questions: int = Field(5, ge=1, le=20) # 5, 10, or 20
    topic: Optional[str] = None # Optional sub-topic focus


class QuizQuestionOut(BaseModel):
    id: int
    question_text: str
    options: List[str]

    class Config:
        from_attributes = True


class QuizQuestionDetailedOut(BaseModel):
    id: int
    question_text: str
    options: List[str]
    correct_option_index: int
    explanation: str

    class Config:
        from_attributes = True


class QuizOut(BaseModel):
    id: int
    title: str
    difficulty: str
    total_questions: int
    created_at: datetime
    document_id: Optional[int] = None
    questions: List[QuizQuestionOut] = []

    class Config:
        from_attributes = True


class QuizAnswerSubmission(BaseModel):
    question_id: int
    selected_option_index: int # 0, 1, 2, 3


class QuizSubmissionRequest(BaseModel):
    answers: List[QuizAnswerSubmission]


class QuizQuestionResult(BaseModel):
    question_id: int
    question_text: str
    options: List[str]
    selected_option_index: int
    correct_option_index: int
    is_correct: bool
    explanation: str


class QuizSubmissionResult(BaseModel):
    attempt_id: int
    quiz_id: int
    score: int
    total_questions: int
    percentage: float
    grade: str
    results: List[QuizQuestionResult]


class QuizAttemptOut(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    difficulty: str
    score: int
    total_questions: int
    percentage: float
    completed_at: datetime

    class Config:
        from_attributes = True
