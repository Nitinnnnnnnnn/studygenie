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
        # Initialize persistent ChromaDB
        # ============================================================

        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_DIR,
            settings=ChromaSettings(
                anonymized_telemetry=False
            )
        )

        # ============================================================
        # ChromaDB built-in embedding function
        #
        # This avoids SentenceTransformer/PyTorch/NVIDIA
        # dependencies and keeps deployment memory lower.
        # ============================================================

        self.embedding_function = DefaultEmbeddingFunction()

        self.collection_name = "studygenie_knowledge_base_v2"

        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine"
            },
            embedding_function=self.embedding_function
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
        Extract text from a PDF page by page.

        Returns:
            [
                {
                    "page_number": 1,
                    "text": "..."
                },
                ...
            ]
        """

        pages = []

        try:

            reader = pypdf.PdfReader(
                file_path
            )

            total_pdf_pages = len(reader.pages)

            logger.info(
                f"Starting text extraction: "
                f"{total_pdf_pages} PDF pages"
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

                # Log progress every 50 pages
                if page_idx % 50 == 0:

                    logger.info(
                        f"Extracted text from "
                        f"{page_idx}/{total_pdf_pages} pages"
                    )

            logger.info(
                f"PDF extraction complete: "
                f"{len(pages)} pages contained text"
            )

            return pages

        except Exception as e:

            logger.error(
                f"Error reading PDF file "
                f"{file_path}: {e}"
            )

            raise RuntimeError(
                f"Could not parse PDF: {str(e)}"
            )

    # ================================================================
    # TEXT CHUNKING
    # ================================================================

    def chunk_text(
        self,
        pages: List[Dict[str, Any]],
        chunk_size: int = 900,
        chunk_overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Split page text into smaller overlapping chunks.

        900-character chunks reduce the total number of chunks
        compared with the previous 700-character configuration,
        which reduces the number of embeddings that must be generated.
        """

        chunks = []

        chunk_counter = 0

        for page_data in pages:

            page_num = page_data["page_number"]

            text = page_data["text"]

            # --------------------------------------------------------
            # Small page
            # --------------------------------------------------------

            if len(text) <= chunk_size:

                chunks.append(
                    {
                        "chunk_index": chunk_counter,
                        "page_number": page_num,
                        "text": text
                    }
                )

                chunk_counter += 1

                continue

            # --------------------------------------------------------
            # Larger page
            # --------------------------------------------------------

            start = 0

            while start < len(text):

                end = start + chunk_size

                chunk_str = text[start:end]

                # ----------------------------------------------------
                # Try to end the chunk at a sentence boundary
                # ----------------------------------------------------

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

                # ----------------------------------------------------
                # Ignore extremely small chunks
                # ----------------------------------------------------

                if len(clean_chunk) > 30:

                    chunks.append(
                        {
                            "chunk_index": chunk_counter,
                            "page_number": page_num,
                            "text": clean_chunk
                        }
                    )

                    chunk_counter += 1

                # ----------------------------------------------------
                # Move forward while keeping overlap
                # ----------------------------------------------------

                next_start = (
                    end - chunk_overlap
                )

                if next_start <= start:

                    next_start = (
                        start + chunk_size
                    )

                start = next_start

        logger.info(
            f"Chunking complete: "
            f"{len(chunks)} chunks generated"
        )

        return chunks

    # ================================================================
    # MEMORY-EFFICIENT CHUNK INDEXING
    # ================================================================

    def index_chunks(
        self,
        doc_id: int,
        user_id: int,
        filename: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Index chunks into ChromaDB using controlled batches.

        Batch size is increased from 8 to 32 to reduce the number
        of ChromaDB operations while remaining reasonable for
        Render's limited memory.
        """

        if not chunks:

            return 0

        # ------------------------------------------------------------
        # Optimized batch size
        # ------------------------------------------------------------

        BATCH_SIZE = 32

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

            # --------------------------------------------------------
            # Create unique IDs
            # --------------------------------------------------------

            ids = [
                (
                    f"user_{user_id}_"
                    f"doc_{doc_id}_"
                    f"chunk_{c['chunk_index']}"
                )
                for c in batch
            ]

            # --------------------------------------------------------
            # Extract document text
            # --------------------------------------------------------

            documents = [
                c["text"]
                for c in batch
            ]

            # --------------------------------------------------------
            # Create metadata
            # --------------------------------------------------------

            metadatas = [
                {
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "filename": filename,
                    "page": c["page_number"],
                    "chunk_index": c["chunk_index"]
                }
                for c in batch
            ]

            batch_end = min(
                start + BATCH_SIZE,
                total_chunks
            )

            logger.info(
                f"Indexing chunks "
                f"{start + 1}-{batch_end} "
                f"of {total_chunks}"
            )

            # --------------------------------------------------------
            # Chroma generates embeddings for this batch
            # --------------------------------------------------------

            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

            # --------------------------------------------------------
            # Release temporary references
            # --------------------------------------------------------

            del batch
            del ids
            del documents
            del metadatas

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
        Process, chunk and store a document in ChromaDB.

        This method is kept for compatibility with existing
        code that may still call index_document().
        """

        logger.info(
            f"Starting PDF processing: {filename}"
        )

        # ------------------------------------------------------------
        # Extract text
        # ------------------------------------------------------------

        pages = self.extract_text_from_pdf(
            file_path
        )

        if not pages:

            raise ValueError(
                "The uploaded PDF has no extractable text."
            )

        logger.info(
            f"Extracted {len(pages)} pages "
            f"from {filename}"
        )

        # ------------------------------------------------------------
        # Create chunks
        # ------------------------------------------------------------

        chunks = self.chunk_text(
            pages
        )

        # Release page data
        del pages

        if not chunks:

            raise ValueError(
                "No text chunks could be generated "
                "from the PDF."
            )

        logger.info(
            f"Generated {len(chunks)} chunks "
            f"for {filename}"
        )

        # ------------------------------------------------------------
        # Index using controlled batches
        # ------------------------------------------------------------

        total_chunks = self.index_chunks(
            doc_id=doc_id,
            user_id=user_id,
            filename=filename,
            chunks=chunks
        )

        # Release chunk data
        del chunks

        return total_chunks

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

        ChromaDB automatically generates the embedding for
        the query using the configured embedding function.
        """

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
        # Check if results exist
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

            # --------------------------------------------------------
            # Convert results into application format
            # --------------------------------------------------------

            for doc_text, meta, dist in zip(
                docs,
                metas,
                distances
            ):

                # ----------------------------------------------------
                # Convert cosine distance to similarity
                # ----------------------------------------------------

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
        Fetch representative document chunks for quiz generation.

        The number of chunks is intentionally limited so that
        very large PDFs do not create unnecessarily large prompts.
        """

        # ------------------------------------------------------------
        # Filter by user
        # ------------------------------------------------------------

        where_clause = {
            "user_id": {
                "$eq": user_id
            }
        }

        # ------------------------------------------------------------
        # Optionally filter by specific document
        # ------------------------------------------------------------

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

        # ------------------------------------------------------------
        # Fetch limited number of chunks
        # ------------------------------------------------------------

        data = self.collection.get(
            where=where_clause,
            limit=max_chunks,
            include=[
                "documents",
                "metadatas"
            ]
        )

        # ------------------------------------------------------------
        # No data found
        # ------------------------------------------------------------

        if (
            not data
            or not data.get("documents")
        ):

            return ""

        # ------------------------------------------------------------
        # Combine retrieved chunks into one context string
        # ------------------------------------------------------------

        return "\n\n".join(
            data["documents"]
        )


# ====================================================================
# GLOBAL RAG SERVICE INSTANCE
# ====================================================================

rag_service = RAGService()