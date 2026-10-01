import re
import uuid
import logging
from typing import List, Dict, Any, Optional

import pypdf

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    PayloadSchemaType,
)

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.config import settings


logger = logging.getLogger(__name__)


class RAGService:

    def __init__(self):
        # ============================================================
        # Lazy Qdrant initialization
        # ============================================================

        self.qdrant_client = None
        self.embedding_function = None

        self.collection_name = "studygenie_knowledge_base"

        logger.info(
            "RAGService created - Qdrant initialization deferred."
        )

    # ================================================================
    # QDRANT INITIALIZATION
    # ================================================================

    def _ensure_qdrant(self):
        """
        Initialize Qdrant and the embedding model only when
        RAG functionality needs them.
        """

        if self.qdrant_client is not None:
            return

        logger.info("Initializing Qdrant and embedding model...")

        if not settings.QDRANT_URL:
            raise RuntimeError(
                "QDRANT_URL is not configured."
            )

        if not settings.QDRANT_API_KEY:
            raise RuntimeError(
                "QDRANT_API_KEY is not configured."
            )

        # ------------------------------------------------------------
        # Connect to Qdrant Cloud
        # ------------------------------------------------------------

        self.qdrant_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY
        )

        # ------------------------------------------------------------
        # Local embedding model
        #
        # Chroma's DefaultEmbeddingFunction uses
        # all-MiniLM-L6-v2 and produces 384-dimensional vectors.
        # ------------------------------------------------------------

        self.embedding_function = DefaultEmbeddingFunction()

        # ------------------------------------------------------------
        # Create collection if it does not already exist
        # ------------------------------------------------------------

        if not self.qdrant_client.collection_exists(
            self.collection_name
        ):

            logger.info(
                f"Creating Qdrant collection: "
                f"{self.collection_name}"
            )

            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )

            logger.info(
                f"Qdrant collection created: "
                f"{self.collection_name}"
            )

        else:

            logger.info(
                f"Qdrant collection already exists: "
                f"{self.collection_name}"
            )

        # ------------------------------------------------------------
        # Create payload indexes
        #
        # These are required because we filter by user_id and doc_id.
        # ------------------------------------------------------------

        try:

            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema=PayloadSchemaType.INTEGER
            )

            logger.info(
                "Qdrant payload index ready: user_id"
            )

        except Exception as e:

            logger.info(
                f"user_id payload index already exists "
                f"or could not be recreated: {e}"
            )

        try:

            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="doc_id",
                field_schema=PayloadSchemaType.INTEGER
            )

            logger.info(
                "Qdrant payload index ready: doc_id"
            )

        except Exception as e:

            logger.info(
                f"doc_id payload index already exists "
                f"or could not be recreated: {e}"
            )

        logger.info(
            "Qdrant initialization complete."
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

        Kept for compatibility with existing code.

        For large PDFs, prefer process_pdf_page_by_page()
        because this method keeps all extracted pages in memory.
        """

        pages = []

        try:

            reader = pypdf.PdfReader(
                file_path
            )

            total_pages = len(
                reader.pages
            )

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

        Kept for compatibility with existing code.

        For large PDFs, use process_pdf_page_by_page().
        """

        chunks = []

        chunk_counter = 0

        for page_data in pages:

            page_num = page_data[
                "page_number"
            ]

            text = page_data[
                "text"
            ]

            page_chunks = self._chunk_single_page(
                text=text,
                page_number=page_num,
                starting_index=chunk_counter,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            chunks.extend(
                page_chunks
            )

            chunk_counter += len(
                page_chunks
            )

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

            chunk_str = text[
                start:end
            ]

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

            clean_chunk = (
                chunk_str.strip()
            )

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
        Index one small batch into Qdrant.

        Qdrant point IDs must be either:
        - unsigned integers
        - UUIDs

        Therefore deterministic UUIDs are used here.
        """

        if not batch:
            return

        self._ensure_qdrant()

        # ------------------------------------------------------------
        # Extract text
        # ------------------------------------------------------------

        documents = [
            chunk["text"]
            for chunk in batch
        ]

        # ------------------------------------------------------------
        # Generate embeddings
        # ------------------------------------------------------------

        embeddings = (
            self.embedding_function(
                documents
            )
        )

        # ------------------------------------------------------------
        # Create Qdrant points
        # ------------------------------------------------------------

        points = []

        for chunk, embedding in zip(
            batch,
            embeddings
        ):

            chunk_index = chunk[
                "chunk_index"
            ]

            # --------------------------------------------------------
            # Deterministic UUID
            #
            # Same user + document + chunk always gets
            # the same UUID.
            # --------------------------------------------------------

            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    (
                        f"user_{user_id}_"
                        f"doc_{doc_id}_"
                        f"chunk_{chunk_index}"
                    )
                )
            )

            payload = {
                "user_id": user_id,
                "doc_id": doc_id,
                "filename": filename,
                "page": chunk[
                    "page_number"
                ],
                "chunk_index": chunk_index,
                "text": chunk[
                    "text"
                ]
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            )

        # ------------------------------------------------------------
        # Upload to Qdrant
        # ------------------------------------------------------------

        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True
        )

        logger.info(
            f"Indexed {len(points)} chunks "
            f"into Qdrant for doc_id={doc_id}"
        )

        # ------------------------------------------------------------
        # Release temporary objects
        # ------------------------------------------------------------

        del documents
        del embeddings
        del points

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
            small Qdrant batch
             ↓
            release memory
             ↓
            next page
        """

        total_pages = 0
        pages_with_text = 0
        total_chunks = 0

        batch = []

        reader = None

        try:

            reader = pypdf.PdfReader(
                file_path
            )

            total_pages = len(
                reader.pages
            )

            logger.info(
                f"Starting memory-efficient "
                f"PDF processing: {filename}"
            )

            logger.info(
                f"Total PDF pages: "
                f"{total_pages}"
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

                del page_text

                # ----------------------------------------------------
                # Add chunks to small batch
                # ----------------------------------------------------

                for chunk in page_chunks:

                    batch.append(
                        chunk
                    )

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

                        batch_end = (
                            total_chunks
                        )

                        logger.info(
                            f"Indexing chunks "
                            f"{batch_start}-"
                            f"{batch_end} "
                            f"of {filename}"
                        )

                        self._index_batch(
                            doc_id=doc_id,
                            user_id=user_id,
                            filename=filename,
                            batch=batch
                        )

                        batch.clear()

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
                        f"{page_index}/"
                        f"{total_pages} pages | "
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
                    f"{batch_start}-"
                    f"{batch_end}"
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
                f"pages_with_text="
                f"{pages_with_text} | "
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

            batch.clear()

            raise

        finally:

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
        """

        if not chunks:
            return 0

        BATCH_SIZE = 8

        total_chunks = len(
            chunks
        )

        logger.info(
            f"Starting Qdrant indexing: "
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

        Uses page-by-page processing.
        """

        logger.info(
            f"Starting memory-efficient "
            f"PDF processing: {filename}"
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

        return result[
            "chunk_count"
        ]

    # ================================================================
    # DELETE DOCUMENT VECTORS
    # ================================================================

    def delete_document_vectors(
        self,
        doc_id: int,
        user_id: int
    ):
        """
        Remove all Qdrant vectors belonging to a document.
        """

        self._ensure_qdrant()

        try:

            delete_filter = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(
                            value=doc_id
                        )
                    ),
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(
                            value=user_id
                        )
                    )
                ]
            )

            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter,
                wait=True
            )

            logger.info(
                f"Deleted Qdrant vectors for "
                f"user_id={user_id}, "
                f"doc_id={doc_id}"
            )

        except Exception as e:

            logger.warning(
                f"Failed to delete Qdrant vectors "
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
        Retrieve the most relevant chunks from Qdrant.
        """

        self._ensure_qdrant()

        # ------------------------------------------------------------
        # Create query embedding
        # ------------------------------------------------------------

        query_embedding = (
            self.embedding_function(
                [query]
            )[0]
        )

        # ------------------------------------------------------------
        # Build Qdrant filter
        # ------------------------------------------------------------

        filter_conditions = [
            FieldCondition(
                key="user_id",
                match=MatchValue(
                    value=user_id
                )
            )
        ]

        if doc_ids:

            if len(doc_ids) == 1:

                filter_conditions.append(
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(
                            value=doc_ids[0]
                        )
                    )
                )

            else:

                filter_conditions.append(
                    FieldCondition(
                        key="doc_id",
                        match=MatchAny(
                            any=doc_ids
                        )
                    )
                )

        query_filter = Filter(
            must=filter_conditions
        )

        # ------------------------------------------------------------
        # Query Qdrant
        # ------------------------------------------------------------

        results = (
            self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True
            )
        )

        passages = []

        # ------------------------------------------------------------
        # Process results
        # ------------------------------------------------------------

        for result in results.points:

            payload = (
                result.payload or {}
            )

            passages.append(
                {
                    "doc_id": payload.get(
                        "doc_id"
                    ),
                    "filename": payload.get(
                        "filename"
                    ),
                    "page": payload.get(
                        "page"
                    ),
                    "chunk_text": payload.get(
                        "text",
                        ""
                    ),
                    "score": round(
                        float(result.score),
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
        Fetch a limited number of document chunks.

        Used by quiz generation.
        """

        self._ensure_qdrant()

        # ------------------------------------------------------------
        # Build filter
        # ------------------------------------------------------------

        filter_conditions = [
            FieldCondition(
                key="user_id",
                match=MatchValue(
                    value=user_id
                )
            )
        ]

        if doc_id is not None:

            filter_conditions.append(
                FieldCondition(
                    key="doc_id",
                    match=MatchValue(
                        value=doc_id
                    )
                )
            )

        scroll_filter = Filter(
            must=filter_conditions
        )

        # ------------------------------------------------------------
        # Scroll Qdrant
        # ------------------------------------------------------------

        points, next_offset = (
            self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=max_chunks,
                with_payload=True,
                with_vectors=False
            )
        )

        if not points:
            return ""

        documents = []

        for point in points:

            payload = (
                point.payload or {}
            )

            text = payload.get(
                "text",
                ""
            )

            if text:
                documents.append(text)

        return "\n\n".join(
            documents
        )


# ====================================================================
# GLOBAL RAG SERVICE INSTANCE
# ====================================================================

rag_service = RAGService()