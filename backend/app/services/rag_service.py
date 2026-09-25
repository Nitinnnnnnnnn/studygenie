import os
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
        # This replaces SentenceTransformer/PyTorch.
        # Chroma handles the embedding generation internally.
        # ============================================================

        self.embedding_function = DefaultEmbeddingFunction()

        self.collection_name = "studygenie_knowledge_base_v2"

        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_function
        )

        logger.info(
            f"ChromaDB collection initialized: {self.collection_name}"
        )

    # ================================================================
    # PDF TEXT EXTRACTION
    # ================================================================

    def extract_text_from_pdf(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """Extract text from a PDF page by page."""

        pages = []

        try:
            reader = pypdf.PdfReader(file_path)

            for page_idx, page in enumerate(reader.pages, 1):

                text = page.extract_text() or ""

                clean_text = re.sub(
                    r'\s+',
                    ' ',
                    text
                ).strip()

                if clean_text:

                    pages.append(
                        {
                            "page_number": page_idx,
                            "text": clean_text
                        }
                    )

            return pages

        except Exception as e:

            logger.error(
                f"Error reading PDF file {file_path}: {e}"
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
        chunk_size: int = 700,
        chunk_overlap: int = 150
    ) -> List[Dict[str, Any]]:
        """Split page texts into overlapping chunks."""

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

                # Try to break at a sentence boundary

                if end < len(text):

                    last_period = max(
                        chunk_str.rfind(". "),
                        chunk_str.rfind(".\n"),
                        chunk_str.rfind("? "),
                        chunk_str.rfind("! ")
                    )

                    if last_period > chunk_size // 2:

                        end = start + last_period + 1

                        chunk_str = text[start:end]

                clean_chunk = chunk_str.strip()

                if len(clean_chunk) > 30:

                    chunks.append(
                        {
                            "chunk_index": chunk_counter,
                            "page_number": page_num,
                            "text": clean_chunk
                        }
                    )

                    chunk_counter += 1

                start += (
                    chunk_size - chunk_overlap
                )

        return chunks

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

        ChromaDB automatically generates embeddings using
        its configured embedding function.
        """

        pages = self.extract_text_from_pdf(
            file_path
        )

        if not pages:

            raise ValueError(
                "The uploaded PDF has no extractable text."
            )

        chunks = self.chunk_text(pages)

        if not chunks:

            raise ValueError(
                "No text chunks could be generated from the PDF."
            )

        # ------------------------------------------------------------
        # Prepare ChromaDB data
        # ------------------------------------------------------------

        ids = [
            f"user_{user_id}_doc_{doc_id}_chunk_{c['chunk_index']}"
            for c in chunks
        ]

        documents = [
            c["text"]
            for c in chunks
        ]

        metadatas = [
            {
                "user_id": user_id,
                "doc_id": doc_id,
                "filename": filename,
                "page": c["page_number"],
                "chunk_index": c["chunk_index"]
            }
            for c in chunks
        ]

        # ------------------------------------------------------------
        # IMPORTANT:
        #
        # We no longer manually generate embeddings.
        #
        # ChromaDB automatically embeds the documents.
        # ------------------------------------------------------------

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        logger.info(
            f"Indexed {len(chunks)} chunks for {filename}"
        )

        return len(chunks)

    # ================================================================
    # DELETE DOCUMENT VECTORS
    # ================================================================

    def delete_document_vectors(
        self,
        doc_id: int,
        user_id: int
    ):
        """Remove all vectors belonging to a document."""

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
        """Retrieve the most relevant chunks."""

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
        # Chroma automatically embeds the query
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

                # Cosine distance -> similarity

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
        """Fetch representative chunks for quiz generation."""

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


rag_service = RAGService()