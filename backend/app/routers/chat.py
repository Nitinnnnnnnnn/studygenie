import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app.schemas import (
    ChatSessionCreate, ChatSessionOut, ChatSessionSummary,
    ChatMessageOut, ChatQueryRequest
)
from app.auth.deps import get_current_user
from app.services.rag_service import rag_service
from app.services.mistral_service import mistral_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.get("/sessions", response_model=List[ChatSessionSummary])
def get_user_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all chat sessions for the current user."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        ChatSessionSummary(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=len(s.messages)
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=ChatSessionOut)
def create_chat_session(
    session_in: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new chat session."""
    session = ChatSession(
        user_id=current_user.id,
        title=session_in.title or "New Study Session"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
def get_chat_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full message history for a specific chat session."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a chat session and all its messages."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    db.delete(session)
    db.commit()
    return {"message": "Chat session deleted successfully."}


@router.post("/sessions/{session_id}/ask", response_model=ChatMessageOut)
def ask_question(
    session_id: int,
    query_req: ChatQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute a RAG query: retrieve relevant chunks, call Mistral, and save response."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    question = query_req.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty.")

    # 1. Save user question message
    user_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        sender="user",
        content=question,
        sources=[]
    )
    db.add(user_msg)

    # 2. Retrieve top-k context passages from ChromaDB
    retrieved_passages = rag_service.query_similar_chunks(
        query=question,
        user_id=current_user.id,
        doc_ids=query_req.document_ids,
        top_k=4
    )

    # 3. Format previous messages for conversation context
    past_messages = [
        {"sender": m.sender, "content": m.content}
        for m in session.messages[-4:]
    ]

    # 4. Generate grounded answer via Mistral
    if not retrieved_passages:
        assistant_content = (
            "I couldn't find any relevant sections in your uploaded study notes for this question. "
            "Please make sure you have uploaded the relevant PDF documents, or try asking in different words."
        )
        sources_data = []
    else:
        assistant_content = mistral_service.generate_rag_response(
            context_passages=retrieved_passages,
            question=question,
            chat_history=past_messages
        )
        sources_data = [
            {
                "doc_id": p["doc_id"],
                "filename": p["filename"],
                "page": p["page"],
                "chunk_text": p["chunk_text"],
                "score": p.get("score")
            }
            for p in retrieved_passages
        ]

    # 5. Save assistant response
    assistant_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        sender="assistant",
        content=assistant_content
    )
    assistant_msg.sources = sources_data
    db.add(assistant_msg)

    # 6. Auto-update session title if it's new
    if session.title == "New Study Session" and len(session.messages) <= 2:
        clean_title = question[:35] + ("..." if len(question) > 35 else "")
        session.title = clean_title

    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg
