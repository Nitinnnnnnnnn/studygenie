import re
import logging
from typing import List, Dict, Any, Optional

import pypdf
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.config import settings


logger = logging.getLogger(__name__)


class RAGService:

    def __init__(self):

        # ============================================================
        # Lazy ChromaDB initialization
        # ============================================================
        # Chroma and the local embedding model are NOT initialized
        # during FastAPI startup. They are initialized only when
        # upload, search, delete, or quiz/RAG functionality needs them.
        # This makes the normal application startup much faster.

        self.chroma_client = None
        self.collection = None
        self.embedding_function = None

        self.collection_name = (
            "studygenie_knowledge_base_v2"
        )

        logger.info(
            "RAGService created - ChromaDB initialization deferred."
        )

    def _ensure_chroma(self):
        """Initialize ChromaDB only when RAG functionality needs it."""

        if self.collection is not None:
            return

        logger.info("Initializing ChromaDB and embedding model...")

        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_DIR,
            settings=ChromaSettings(
                anonymized_telemetry=False
            )
        )

        self.embedding_function = DefaultEmbeddingFunction()

        self.collection = (
            self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine"
                },
                embedding_function=self.embedding_function
            )
        )

        logger.info(
            f"ChromaDB collection initialized: "
            f"{self.collection_name}"
        )

    # ================================================================
    # PDF TEXT EXTRACTION
    # ================================================================

    def extract_text_from_pdf(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Extract text from the entire PDF.

        This method is kept for compatibility with existing code.

        NOTE:
        For large PDFs, prefer process_pdf_page_by_page()
        because this method keeps all extracted pages in memory.
        """

        pages = []

        try:

            reader = pypdf.PdfReader(
                file_path
            )

            total_pages = len(reader.pages)

            logger.info(
                f"Starting PDF extraction: "
                f"{total_pages} pages"
            )

            for page_idx, page in enumerate(
                reader.pages,
                1
            ):

                text = page.extract_text() or ""

                clean_text = re.sub(
                    r"\s+",
                    " ",
                    text
                ).strip()

                if clean_text:

                    pages.append(
                        {
                            "page_number": page_idx,
                            "text": clean_text
                        }
                    )

                if page_idx % 50 == 0:

                    logger.info(
                        f"Extracted "
                        f"{page_idx}/{total_pages} pages"
                    )

            logger.info(
                f"PDF extraction complete: "
                f"{len(pages)} pages contained text"
            )

            return pages

        except Exception as e:

            logger.exception(
                f"Error reading PDF file "
                f"{file_path}"
            )

            raise RuntimeError(
                f"Could not parse PDF: {str(e)}"
            )

    # ================================================================
    # EXTRACT SINGLE PAGE
    # ================================================================

    def extract_page_text(
        self,
        page,
        page_number: int
    ) -> Optional[str]:
        """
        Extract and clean text from one PDF page.

        Only one page's text is kept in memory at a time.
        """

        try:

            text = page.extract_text() or ""

            clean_text = re.sub(
                r"\s+",
                " ",
                text
            ).strip()

            if not clean_text:

                return None

            return clean_text

        except Exception as e:

            logger.warning(
                f"Could not extract page "
                f"{page_number}: {e}"
            )

            return None

    # ================================================================
    # TEXT CHUNKING
    # ================================================================

    def chunk_text(
        self,
        pages: List[Dict[str, Any]],
        chunk_size: int = 800,
        chunk_overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Split pages into overlapping chunks.

        This method is kept for compatibility with existing code.

        For large PDFs, use process_pdf_page_by_page() instead.
        """

        chunks = []

        chunk_counter = 0

        for page_data in pages:

            page_num = page_data["page_number"]

            text = page_data["text"]

            page_chunks = self._chunk_single_page(
                text=text,
                page_number=page_num,
                starting_index=chunk_counter,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            chunks.extend(page_chunks)

            chunk_counter += len(page_chunks)

        logger.info(
            f"Chunking complete: "
            f"{len(chunks)} chunks generated"
        )

        return chunks

    # ================================================================
    # CHUNK ONE PAGE
    # ================================================================

    def _chunk_single_page(
        self,
        text: str,
        page_number: int,
        starting_index: int,
        chunk_size: int = 800,
        chunk_overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Create chunks from ONE page only.

        This prevents the entire PDF from being converted into
        chunks at once.
        """

        chunks = []

        if not text:

            return chunks

        # ------------------------------------------------------------
        # Small page
        # ------------------------------------------------------------

        if len(text) <= chunk_size:

            if len(text) > 30:

                chunks.append(
                    {
                        "chunk_index": starting_index,
                        "page_number": page_number,
                        "text": text
                    }
                )

            return chunks

        # ------------------------------------------------------------
        # Large page
        # ------------------------------------------------------------

        start = 0

        chunk_counter = starting_index

        while start < len(text):

            end = start + chunk_size

            chunk_str = text[start:end]

            # --------------------------------------------------------
            # Try to end at sentence boundary
            # --------------------------------------------------------

            if end < len(text):

                last_period = max(
                    chunk_str.rfind(". "),
                    chunk_str.rfind("? "),
                    chunk_str.rfind("! ")
                )

                if last_period > chunk_size // 2:

                    end = (
                        start
                        + last_period
                        + 1
                    )

                    chunk_str = text[
                        start:end
                    ]

            clean_chunk = chunk_str.strip()

            # --------------------------------------------------------
            # Ignore extremely small chunks
            # --------------------------------------------------------

            if len(clean_chunk) > 30:

                chunks.append(
                    {
                        "chunk_index": chunk_counter,
                        "page_number": page_number,
                        "text": clean_chunk
                    }
                )

                chunk_counter += 1

            # --------------------------------------------------------
            # Maintain overlap
            # --------------------------------------------------------

            next_start = (
                end - chunk_overlap
            )

            if next_start <= start:

                next_start = (
                    start + chunk_size
                )

            start = next_start

        return chunks

    # ================================================================
    # INDEX SMALL BATCH
    # ================================================================

    def _index_batch(
        self,
        doc_id: int,
        user_id: int,
        filename: str,
        batch: List[Dict[str, Any]]
    ):
        """
        Index one small batch into ChromaDB.

        Batch size is intentionally small because Render's
        free instance has limited memory.
        """

        if not batch:

            return

        self._ensure_chroma()

        ids = [
            (
                f"user_{user_id}_"
                f"doc_{doc_id}_"
                f"chunk_{chunk['chunk_index']}"
            )
            for chunk in batch
        ]

        documents = [
            chunk["text"]
            for chunk in batch
        ]

        metadatas = [
            {
                "user_id": user_id,
                "doc_id": doc_id,
                "filename": filename,
                "page": chunk["page_number"],
                "chunk_index": chunk["chunk_index"]
            }
            for chunk in batch
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        # Explicitly release temporary objects
        del ids
        del documents
        del metadatas

    # ================================================================
    # PAGE-BY-PAGE PDF PROCESSING
    # ================================================================

    def process_pdf_page_by_page(
        self,
        doc_id: int,
        user_id: int,
        filename: str,
        file_path: str,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        batch_size: int = 8
    ) -> Dict[str, int]:
        """
        Process a PDF page-by-page.

        MEMORY-EFFICIENT PIPELINE:

            PDF
             ↓
            one page
             ↓
            extract text
             ↓
            create chunks
             ↓
            small ChromaDB batch
             ↓
            release memory
             ↓
            next page

        The entire PDF's pages and chunks are NEVER stored
        in memory simultaneously.
        """

        total_pages = 0
        pages_with_text = 0
        total_chunks = 0

        # Temporary batch containing only a few chunks
        batch = []

        try:

            reader = pypdf.PdfReader(
                file_path
            )

            total_pages = len(
                reader.pages
            )

            logger.info(
                f"Starting memory-efficient PDF processing: "
                f"{filename}"
            )

            logger.info(
                f"Total PDF pages: {total_pages}"
            )

            # --------------------------------------------------------
            # Process ONE page at a time
            # --------------------------------------------------------

            for page_index, page in enumerate(
                reader.pages,
                1
            ):

                # ----------------------------------------------------
                # Extract only this page
                # ----------------------------------------------------

                page_text = self.extract_page_text(
                    page=page,
                    page_number=page_index
                )

                if not page_text:

                    continue

                pages_with_text += 1

                # ----------------------------------------------------
                # Chunk only this page
                # ----------------------------------------------------

                page_chunks = self._chunk_single_page(
                    text=page_text,
                    page_number=page_index,
                    starting_index=total_chunks,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )

                # page_text is no longer needed
                del page_text

                # ----------------------------------------------------
                # Add page chunks to small batch
                # ----------------------------------------------------

                for chunk in page_chunks:

                    batch.append(chunk)

                    total_chunks += 1

                    # ------------------------------------------------
                    # Index when batch reaches limit
                    # ------------------------------------------------

                    if len(batch) >= batch_size:

                        batch_start = (
                            total_chunks
                            - len(batch)
                            + 1
                        )

                        batch_end = total_chunks

                        logger.info(
                            f"Indexing chunks "
                            f"{batch_start}-{batch_end} "
                            f"of {filename}"
                        )

                        self._index_batch(
                            doc_id=doc_id,
                            user_id=user_id,
                            filename=filename,
                            batch=batch
                        )

                        # Completely release batch
                        batch.clear()

                # ----------------------------------------------------
                # Release page chunks
                # ----------------------------------------------------

                del page_chunks

                # ----------------------------------------------------
                # Progress logging
                # ----------------------------------------------------

                if (
                    page_index % 10 == 0
                    or page_index == total_pages
                ):

                    logger.info(
                        f"Processed "
                        f"{page_index}/{total_pages} pages | "
                        f"chunks indexed/queued: "
                        f"{total_chunks}"
                    )

            # --------------------------------------------------------
            # Index remaining chunks
            # --------------------------------------------------------

            if batch:

                batch_start = (
                    total_chunks
                    - len(batch)
                    + 1
                )

                batch_end = total_chunks

                logger.info(
                    f"Indexing final chunks "
                    f"{batch_start}-{batch_end}"
                )

                self._index_batch(
                    doc_id=doc_id,
                    user_id=user_id,
                    filename=filename,
                    batch=batch
                )

                batch.clear()

            logger.info(
                f"PDF processing complete: "
                f"{filename} | "
                f"pages={total_pages} | "
                f"pages_with_text={pages_with_text} | "
                f"chunks={total_chunks}"
            )

            return {
                "total_pages": total_pages,
                "pages_with_text": pages_with_text,
                "chunk_count": total_chunks
            }

        except Exception as e:

            logger.exception(
                f"Failed processing PDF "
                f"{filename}: {e}"
            )

            # Release temporary memory
            batch.clear()

            raise

        finally:

            # --------------------------------------------------------
            # Release PDF reader
            # --------------------------------------------------------

            try:
                del reader
            except Exception:
                pass

            batch.clear()

    # ================================================================
    # INDEX CHUNKS
    # ================================================================

    def index_chunks(
        self,
        doc_id: int,
        user_id: int,
        filename: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Index an already-created list of chunks.

        Kept for compatibility with existing code.

        Uses batch size 8 for low-memory deployments.
        """

        if not chunks:

            return 0

        BATCH_SIZE = 8

        total_chunks = len(chunks)

        logger.info(
            f"Starting ChromaDB indexing: "
            f"{total_chunks} chunks, "
            f"batch size={BATCH_SIZE}"
        )

        for start in range(
            0,
            total_chunks,
            BATCH_SIZE
        ):

            batch = chunks[
                start:start + BATCH_SIZE
            ]

            logger.info(
                f"Indexing chunks "
                f"{start + 1}-"
                f"{min(start + BATCH_SIZE, total_chunks)} "
                f"of {total_chunks}"
            )

            self._index_batch(
                doc_id=doc_id,
                user_id=user_id,
                filename=filename,
                batch=batch
            )

            del batch

        logger.info(
            f"Indexed {total_chunks} chunks "
            f"for {filename}"
        )

        return total_chunks

    # ================================================================
    # INDEX DOCUMENT
    # ================================================================

    def index_document(
        self,
        doc_id: int,
        user_id: int,
        filename: str,
        file_path: str
    ) -> int:
        """
        Memory-efficient document indexing.

        This method now uses page-by-page processing.
        """

        logger.info(
            f"Starting memory-efficient PDF processing: "
            f"{filename}"
        )

        result = self.process_pdf_page_by_page(
            doc_id=doc_id,
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            chunk_size=800,
            chunk_overlap=100,
            batch_size=8
        )

        return result["chunk_count"]

    # ================================================================
    # DELETE DOCUMENT VECTORS
    # ================================================================

    def delete_document_vectors(
        self,
        doc_id: int,
        user_id: int
    ):
        """
        Remove all ChromaDB vectors belonging to a document.
        """

        self._ensure_chroma()

        try:

            self.collection.delete(
                where={
                    "$and": [
                        {
                            "doc_id": {
                                "$eq": doc_id
                            }
                        },
                        {
                            "user_id": {
                                "$eq": user_id
                            }
                        }
                    ]
                }
            )

            logger.info(
                f"Deleted vectors for "
                f"user_id={user_id}, "
                f"doc_id={doc_id}"
            )

        except Exception as e:

            logger.warning(
                f"Failed to delete ChromaDB vectors "
                f"for doc_id={doc_id}: {e}"
            )

    # ================================================================
    # QUERY SIMILAR CHUNKS
    # ================================================================

    def query_similar_chunks(
        self,
        query: str,
        user_id: int,
        doc_ids: Optional[List[int]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant chunks for a query.
        """

        self._ensure_chroma()

        # ------------------------------------------------------------
        # Build metadata filter
        # ------------------------------------------------------------

        if doc_ids and len(doc_ids) == 1:

            where_clause = {
                "$and": [
                    {
                        "user_id": {
                            "$eq": user_id
                        }
                    },
                    {
                        "doc_id": {
                            "$eq": doc_ids[0]
                        }
                    }
                ]
            }

        elif doc_ids and len(doc_ids) > 1:

            where_clause = {
                "$and": [
                    {
                        "user_id": {
                            "$eq": user_id
                        }
                    },
                    {
                        "doc_id": {
                            "$in": doc_ids
                        }
                    }
                ]
            }

        else:

            where_clause = {
                "user_id": {
                    "$eq": user_id
                }
            }

        # ------------------------------------------------------------
        # Query ChromaDB
        # ------------------------------------------------------------

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_clause,
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

        passages = []

        # ------------------------------------------------------------
        # Check results
        # ------------------------------------------------------------

        if (
            results
            and results.get("documents")
            and results["documents"][0]
        ):

            docs = results["documents"][0]

            metas = results["metadatas"][0]

            distances = (
                results["distances"][0]
                if results.get("distances")
                else [0.0] * len(docs)
            )

            for doc_text, meta, dist in zip(
                docs,
                metas,
                distances
            ):

                similarity = max(
                    0.0,
                    1.0 - dist
                )

                passages.append(
                    {
                        "doc_id": meta["doc_id"],
                        "filename": meta["filename"],
                        "page": meta["page"],
                        "chunk_text": doc_text,
                        "score": round(
                            similarity,
                            4
                        )
                    }
                )

        return passages

    # ================================================================
    # FULL DOCUMENT CONTEXT
    # ================================================================

    def get_document_full_context(
        self,
        user_id: int,
        doc_id: Optional[int] = None,
        max_chunks: int = 20
    ) -> str:
        """
        Fetch a limited number of document chunks for quiz generation.
        """

        self._ensure_chroma()

        where_clause = {
            "user_id": {
                "$eq": user_id
            }
        }

        if doc_id:

            where_clause = {
                "$and": [
                    {
                        "user_id": {
                            "$eq": user_id
                        }
                    },
                    {
                        "doc_id": {
                            "$eq": doc_id
                        }
                    }
                ]
            }

        data = self.collection.get(
            where=where_clause,
            limit=max_chunks,
            include=[
                "documents",
                "metadatas"
            ]
        )

        if (
            not data
            or not data.get("documents")
        ):

            return ""

        return "\n\n".join(
            data["documents"]
        )


# ====================================================================
# GLOBAL RAG SERVICE INSTANCE
# ====================================================================

rag_service = RAGService()