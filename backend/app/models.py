import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, default=0) # in bytes
    total_pages = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="documents")
    quizzes = relationship("Quiz", back_populates="document", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="New Study Session")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender = Column(String(20), nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    _sources = Column("sources", Text, nullable=True) # JSON serialized list of citation objects
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    @property
    def sources(self):
        if self._sources:
            try:
                return json.loads(self._sources)
            except Exception:
                return []
        return []

    @sources.setter
    def sources(self, value):
        if value is not None:
            self._sources = json.dumps(value)
        else:
            self._sources = None


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(20), default="Medium") # 'Easy', 'Medium', 'Hard'
    total_questions = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="quizzes")
    document = relationship("Document", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.id")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    _options = Column("options", Text, nullable=False) # JSON list of 4 options
    correct_option_index = Column(Integer, nullable=False) # 0, 1, 2, or 3
    explanation = Column(Text, nullable=False)

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")

    @property
    def options(self):
        if self._options:
            try:
                return json.loads(self._options)
            except Exception:
                return []
        return []

    @options.setter
    def options(self, value):
        self._options = json.dumps(value)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)

    completed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="quiz_attempts")
    quiz = relationship("Quiz", back_populates="attempts")
    answers = relationship(
        "QuizAttemptAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class QuizAttemptAnswer(Base):
    __tablename__ = "quiz_attempt_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False)
    selected_option_index = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    # Relationships
    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("QuizQuestion")
