import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Quiz, QuizAttempt
from app.schemas import (
    QuizGenerateRequest, QuizOut, QuizQuestionDetailedOut,
    QuizSubmissionRequest, QuizSubmissionResult, QuizAttemptOut
)
from app.auth.deps import get_current_user
from app.services.quiz_service import quiz_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["AI Quizzes"])


@router.post("/generate", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    req: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate an AI-powered quiz from uploaded study notes with specified difficulty & count."""
    try:
        quiz = quiz_service.create_quiz(
            db=db,
            user_id=current_user.id,
            req=req
        )
        return quiz
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}"
        )


@router.get("/{quiz_id}", response_model=QuizOut)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a quiz by ID to display questions for taking the test."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == current_user.id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    return quiz


@router.post("/{quiz_id}/submit", response_model=QuizSubmissionResult)
def submit_quiz_answers(
    quiz_id: int,
    submission: QuizSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit quiz answers, compute score, evaluate explanations, and record attempt."""
    try:
        result = quiz_service.evaluate_quiz_submission(
            db=db,
            user_id=current_user.id,
            quiz_id=quiz_id,
            submission=submission
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error submitting quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate quiz: {str(e)}"
        )


@router.get("/history/attempts", response_model=List[QuizAttemptOut])
def get_quiz_attempts_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all previous quiz attempts and scores for the current user."""
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.completed_at.desc())
        .all()
    )
    return [
        QuizAttemptOut(
            id=att.id,
            quiz_id=att.quiz_id,
            quiz_title=att.quiz.title if att.quiz else "Study Quiz",
            difficulty=att.quiz.difficulty if att.quiz else "Medium",
            score=att.score,
            total_questions=att.total_questions,
            percentage=att.percentage,
            completed_at=att.completed_at
        )
        for att in attempts
    ]
