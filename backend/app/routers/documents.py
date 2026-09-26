import os
import shutil
import logging
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Document
from app.schemas import DocumentOut, DocumentUploadResponse
from app.auth.deps import get_current_user
from app.services.rag_service import rag_service
from app.config import settings


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


# ====================================================================
# UPLOAD DOCUMENTS
# ====================================================================

@router.post(
    "/upload",
    response_model=DocumentUploadResponse
)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload one or multiple PDF documents.

    Process:
        1. Save PDF
        2. Extract text
        3. Create chunks
        4. Generate embeddings in batches
        5. Store vectors in ChromaDB
        6. Save document information in PostgreSQL
    """

    # ================================================================
    # Validate files
    # ================================================================

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided."
        )

    uploaded_docs: List[Document] = []

    # ================================================================
    # Create user upload directory
    # ================================================================

    user_upload_dir = os.path.join(
        settings.UPLOAD_DIR,
        f"user_{current_user.id}"
    )

    os.makedirs(
        user_upload_dir,
        exist_ok=True
    )

    # ================================================================
    # Process each uploaded file
    # ================================================================

    for file in files:

        # ------------------------------------------------------------
        # Validate filename
        # ------------------------------------------------------------

        if not file.filename:
            continue

        # ------------------------------------------------------------
        # Only allow PDF files
        # ------------------------------------------------------------

        if not file.filename.lower().endswith(".pdf"):
            continue

        # ------------------------------------------------------------
        # Create file path
        # ------------------------------------------------------------

        file_path = os.path.join(
            user_upload_dir,
            file.filename
        )

        # ============================================================
        # Save uploaded PDF
        # ============================================================

        try:

            with open(
                file_path,
                "wb"
            ) as buffer:

                shutil.copyfileobj(
                    file.file,
                    buffer
                )

        except Exception as e:

            logger.error(
                f"Failed to save {file.filename}: {e}"
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Failed to save "
                    f"{file.filename}."
                )
            )

        file_size = os.path.getsize(
            file_path
        )

        logger.info(
            f"Saved PDF: "
            f"{file.filename} "
            f"({file_size} bytes)"
        )

        # ============================================================
        # Create database document record
        # ============================================================

        doc_record = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            total_pages=0,
            chunk_count=0
        )

        db.add(doc_record)

        # Get database-generated document ID
        db.flush()

        # ============================================================
        # Process PDF
        # ============================================================

        try:

            logger.info(
                f"Starting processing: "
                f"{file.filename}"
            )

            # --------------------------------------------------------
            # Extract PDF text ONCE
            # --------------------------------------------------------

            pages = rag_service.extract_text_from_pdf(
                file_path
            )

            if not pages:
                raise ValueError(
                    "The uploaded PDF has no "
                    "extractable text."
                )

            total_pages = len(pages)

            logger.info(
                f"Extracted "
                f"{total_pages} pages "
                f"from {file.filename}"
            )

            # --------------------------------------------------------
            # Create text chunks
            # --------------------------------------------------------

            chunks = rag_service.chunk_text(
                pages
            )

            # Release page data
            del pages

            if not chunks:
                raise ValueError(
                    "No text chunks could be "
                    "generated from the PDF."
                )

            logger.info(
                f"Generated "
                f"{len(chunks)} chunks "
                f"for {file.filename}"
            )

            # --------------------------------------------------------
            # Index chunks in batches
            #
            # Batch size is controlled inside rag_service.py.
            # --------------------------------------------------------

            chunk_count = rag_service.index_chunks(
                doc_id=doc_record.id,
                user_id=current_user.id,
                filename=file.filename,
                chunks=chunks
            )

            # Release chunk list
            del chunks

            logger.info(
                f"Indexed "
                f"{chunk_count} chunks "
                f"for {file.filename}"
            )

            # --------------------------------------------------------
            # Update database record
            # --------------------------------------------------------

            doc_record.total_pages = total_pages
            doc_record.chunk_count = chunk_count

            # --------------------------------------------------------
            # Commit database transaction
            # --------------------------------------------------------

            db.commit()

            db.refresh(
                doc_record
            )

            uploaded_docs.append(
                doc_record
            )

            logger.info(
                f"Successfully processed "
                f"{file.filename}"
            )

        # ============================================================
        # Processing failed
        # ============================================================

        except Exception as e:

            logger.exception(
                f"Failed to process "
                f"{file.filename}"
            )

            # --------------------------------------------------------
            # Remove partially indexed ChromaDB vectors
            # --------------------------------------------------------

            try:

                rag_service.delete_document_vectors(
                    doc_id=doc_record.id,
                    user_id=current_user.id
                )

                logger.info(
                    f"Cleaned up ChromaDB vectors "
                    f"for failed document "
                    f"{doc_record.id}"
                )

            except Exception as vector_error:

                logger.warning(
                    f"Could not clean up ChromaDB "
                    f"vectors for document "
                    f"{doc_record.id}: "
                    f"{vector_error}"
                )

            # --------------------------------------------------------
            # Roll back database transaction
            # --------------------------------------------------------

            db.rollback()

            # --------------------------------------------------------
            # Remove failed PDF
            # --------------------------------------------------------

            if os.path.exists(file_path):

                try:

                    os.remove(
                        file_path
                    )

                except Exception as cleanup_error:

                    logger.warning(
                        f"Could not remove failed "
                        f"file {file_path}: "
                        f"{cleanup_error}"
                    )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Failed to index "
                    f"{file.filename}: "
                    f"{str(e)}"
                )
            )

        # ============================================================
        # Always close uploaded file
        # ============================================================

        finally:

            try:
                await file.close()

            except Exception:
                pass

    # ================================================================
    # Check whether at least one PDF was processed
    # ================================================================

    if not uploaded_docs:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No valid PDF documents "
                "could be processed."
            )
        )

    # ================================================================
    # Return successful response
    # ================================================================

    return DocumentUploadResponse(
        message=(
            f"Successfully processed and indexed "
            f"{len(uploaded_docs)} document(s)."
        ),
        documents=uploaded_docs
    )


# ====================================================================
# LIST DOCUMENTS
# ====================================================================

@router.get(
    "/",
    response_model=List[DocumentOut]
)
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all documents uploaded by the authenticated user.
    """

    return (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id
        )
        .order_by(
            Document.created_at.desc()
        )
        .all()
    )


# ====================================================================
# DELETE DOCUMENT
# ====================================================================

@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_200_OK
)
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document.

    This removes:
        1. ChromaDB vectors
        2. Physical PDF
        3. PostgreSQL database record
    """

    # ================================================================
    # Find document
    # ================================================================

    doc = (
        db.query(Document)
        .filter(
            Document.id == doc_id,
            Document.user_id == current_user.id
        )
        .first()
    )

    if not doc:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    # ================================================================
    # Delete vectors from ChromaDB
    # ================================================================

    rag_service.delete_document_vectors(
        doc_id=doc.id,
        user_id=current_user.id
    )

    # ================================================================
    # Delete physical PDF
    # ================================================================

    if os.path.exists(
        doc.file_path
    ):

        try:

            os.remove(
                doc.file_path
            )

        except Exception as e:

            logger.warning(
                f"Could not delete physical "
                f"file {doc.file_path}: {e}"
            )

    # ================================================================
    # Delete database record
    # ================================================================

    db.delete(
        doc
    )

    db.commit()

    # ================================================================
    # Return response
    # ================================================================

    return {
        "message": (
            f"Document "
            f"'{doc.filename}' "
            f"deleted successfully."
        )
    }