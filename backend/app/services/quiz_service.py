import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Quiz, QuizQuestion, QuizAttempt, QuizAttemptAnswer, Document
from app.schemas import (
    QuizGenerateRequest, QuizSubmissionRequest,
    QuizSubmissionResult, QuizQuestionResult
)
from app.services.mistral_service import mistral_service
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)


class QuizService:
    def create_quiz(
        self,
        db: Session,
        user_id: int,
        req: QuizGenerateRequest
    ) -> Quiz:
        """Fetch document context, generate MCQ questions via Mistral, and save to DB."""
        # Get context from vector store
        context_text = rag_service.get_document_full_context(
            user_id=user_id,
            doc_id=req.document_id,
            max_chunks=25
        )

        if not context_text:
            raise ValueError("No study notes found to generate quiz from. Please upload a PDF first.")

        # Determine quiz title
        doc_title = "All Notes"
        if req.document_id:
            doc = db.query(Document).filter(Document.id == req.document_id, Document.user_id == user_id).first()
            if doc:
                doc_title = doc.filename

        quiz_title = f"{req.difficulty} Quiz: {doc_title} ({req.total_questions} Questions)"

        # Generate questions via Mistral
        questions_data = mistral_service.generate_quiz_questions(
            context_text=context_text,
            difficulty=req.difficulty,
            total_questions=req.total_questions,
            topic=req.topic
        )

        # Save Quiz entity
        quiz = Quiz(
            user_id=user_id,
            document_id=req.document_id,
            title=quiz_title,
            difficulty=req.difficulty,
            total_questions=len(questions_data)
        )
        db.add(quiz)
        db.flush() # Populate quiz.id

        # Save Quiz Questions
        for q_data in questions_data:
            question = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_option_index=q_data["correct_option_index"],
                explanation=q_data["explanation"]
            )
            db.add(question)

        db.commit()
        db.refresh(quiz)
        return quiz

    def evaluate_quiz_submission(
        self,
        db: Session,
        user_id: int,
        quiz_id: int,
        submission: QuizSubmissionRequest
    ) -> QuizSubmissionResult:
        """Evaluate submitted answers, calculate score & percentage, and save attempt."""
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user_id).first()
        if not quiz:
            raise ValueError("Quiz not found")

        # Map user submitted answers
        submitted_map = {ans.question_id: ans.selected_option_index for ans in submission.answers}

        score = 0
        total_questions = len(quiz.questions)
        results: List[QuizQuestionResult] = []
        attempt_answers: List[QuizAttemptAnswer] = []

        for question in quiz.questions:
            selected_idx = submitted_map.get(question.id, -1)
            is_correct = (selected_idx == question.correct_option_index)
            if is_correct:
                score += 1

            results.append(QuizQuestionResult(
                question_id=question.id,
                question_text=question.question_text,
                options=question.options,
                selected_option_index=selected_idx,
                correct_option_index=question.correct_option_index,
                is_correct=is_correct,
                explanation=question.explanation
            ))

            attempt_answers.append(QuizAttemptAnswer(
                question_id=question.id,
                selected_option_index=selected_idx,
                is_correct=is_correct
            ))

        percentage = round((score / total_questions) * 100, 1) if total_questions > 0 else 0.0

        # Calculate Grade
        if percentage >= 90:
            grade = "A+ (Outstanding)"
        elif percentage >= 80:
            grade = "A (Excellent)"
        elif percentage >= 70:
            grade = "B (Good)"
        elif percentage >= 60:
            grade = "C (Satisfactory)"
        else:
            grade = "Needs Review"

        # Record attempt in DB
        attempt = QuizAttempt(
            user_id=user_id,
            quiz_id=quiz.id,
            score=score,
            total_questions=total_questions,
            percentage=percentage
        )
        db.add(attempt)
        db.flush()

        for ans in attempt_answers:
            ans.attempt_id = attempt.id
            db.add(ans)

        db.commit()

        return QuizSubmissionResult(
            attempt_id=attempt.id,
            quiz_id=quiz.id,
            score=score,
            total_questions=total_questions,
            percentage=percentage,
            grade=grade,
            results=results
        )


quiz_service = QuizService()
