import os
import shutil
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Document
from app.schemas import DocumentOut, DocumentUploadResponse
from app.auth.deps import get_current_user
from app.services.rag_service import rag_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload one or multiple PDF documents, extract text, chunk and index into ChromaDB."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided.")

    uploaded_docs: List[Document] = []

    for file in files:
        # Validate PDF extension
        if not file.filename.lower().endswith(".pdf"):
            continue

        # Create user upload directory
        user_upload_dir = os.path.join(settings.UPLOAD_DIR, f"user_{current_user.id}")
        os.makedirs(user_upload_dir, exist_ok=True)

        # Save file to disk
        file_path = os.path.join(user_upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)

        # Create Document record in DB
        doc_record = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            total_pages=0,
            chunk_count=0
        )
        db.add(doc_record)
        db.flush() # Get doc_record.id

        try:
            # Process & index in ChromaDB
            chunk_count = rag_service.index_document(
                doc_id=doc_record.id,
                user_id=current_user.id,
                filename=file.filename,
                file_path=file_path
            )
            # Count pages
            pages = rag_service.extract_text_from_pdf(file_path)
            doc_record.total_pages = len(pages)
            doc_record.chunk_count = chunk_count

            db.commit()
            db.refresh(doc_record)
            uploaded_docs.append(doc_record)

        except Exception as e:
            logger.error(f"Failed to process document {file.filename}: {e}")
            db.rollback()
            # Clean file if failed
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to index {file.filename}: {str(e)}"
            )

    if not uploaded_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid PDF documents could be processed."
        )

    return DocumentUploadResponse(
        message=f"Successfully processed and indexed {len(uploaded_docs)} document(s).",
        documents=uploaded_docs
    )


@router.get("/", response_model=List[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all documents uploaded by the authenticated user."""
    return db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.created_at.desc()).all()


@router.delete("/{doc_id}", status_code=status.HTTP_200_OK)
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document, remove its file from disk, and clear its vectors from ChromaDB."""
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # 1. Delete vectors from ChromaDB
    rag_service.delete_document_vectors(doc_id=doc.id, user_id=current_user.id)

    # 2. Delete file from disk
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning(f"Could not delete physical file {doc.file_path}: {e}")

    # 3. Delete from DB
    db.delete(doc)
    db.commit()

    return {"message": f"Document '{doc.filename}' deleted successfully."}
