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

    Memory-efficient process:

        1. Save PDF to disk
        2. Create PostgreSQL document record
        3. Read one PDF page at a time
        4. Extract text from the current page
        5. Create chunks from the current page
        6. Index small batches into ChromaDB
        7. Release page/chunk memory
        8. Move to the next page
        9. Save document information in PostgreSQL

    This approach is designed for low-memory deployments
    such as Render's free instance.
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
        # Create PostgreSQL document record
        # ============================================================

        doc_record = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            total_pages=0,
            chunk_count=0
        )

        db.add(
            doc_record
        )

        # Get database-generated document ID
        db.flush()

        # ============================================================
        # Process PDF using memory-efficient RAG pipeline
        # ============================================================

        try:

            logger.info(
                f"Starting memory-efficient processing: "
                f"{file.filename}"
            )

            # --------------------------------------------------------
            # IMPORTANT:
            #
            # Do NOT call:
            #
            # extract_text_from_pdf()
            # chunk_text()
            # index_chunks()
            #
            # here because those methods can keep large amounts
            # of PDF data in memory.
            #
            # Instead process the PDF page-by-page.
            # --------------------------------------------------------

            result = rag_service.process_pdf_page_by_page(
                doc_id=doc_record.id,
                user_id=current_user.id,
                filename=file.filename,
                file_path=file_path,
                chunk_size=800,
                chunk_overlap=100,
                batch_size=8
            )

            # --------------------------------------------------------
            # Get processing results
            # --------------------------------------------------------

            total_pages = result[
                "total_pages"
            ]

            pages_with_text = result[
                "pages_with_text"
            ]

            chunk_count = result[
                "chunk_count"
            ]

            # --------------------------------------------------------
            # Make sure useful text was found
            # --------------------------------------------------------

            if pages_with_text == 0:

                raise ValueError(
                    "The uploaded PDF has no "
                    "extractable text."
                )

            if chunk_count == 0:

                raise ValueError(
                    "No text chunks could be "
                    "generated from the PDF."
                )

            logger.info(
                f"PDF processing complete: "
                f"{file.filename} | "
                f"pages={total_pages} | "
                f"pages_with_text={pages_with_text} | "
                f"chunks={chunk_count}"
            )

            # ========================================================
            # Update document record
            # ========================================================

            doc_record.total_pages = (
                total_pages
            )

            doc_record.chunk_count = (
                chunk_count
            )

            # ========================================================
            # Commit PostgreSQL transaction
            # ========================================================

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
            # Roll back PostgreSQL transaction
            # --------------------------------------------------------

            db.rollback()

            # --------------------------------------------------------
            # Remove failed PDF
            # --------------------------------------------------------

            if os.path.exists(
                file_path
            ):

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
    # Delete PostgreSQL database record
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