import os
import shutil
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.database import SessionLocal
from app.models import Document



BACKUP_DIR = os.path.join(
    os.path.dirname(settings.CHROMA_DB_DIR),
    "chroma_data_mistral_backup"
)


def main():
    print("=" * 70)
    print("StudyGenie - Mistral → MiniLM Embedding Migration")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Check the existing backup
    # ---------------------------------------------------------
    if not os.path.exists(BACKUP_DIR):
        raise RuntimeError(
            f"Backup directory not found: {BACKUP_DIR}\n"
            "Do not continue until the Chroma backup exists."
        )

    print(f"\n✓ Backup found: {BACKUP_DIR}")

    # ---------------------------------------------------------
    # 2. Read existing documents from SQLite
    # ---------------------------------------------------------
    db = SessionLocal()

    try:
        documents = db.query(Document).order_by(Document.id).all()

        print(f"✓ Documents found in database: {len(documents)}")

        if not documents:
            print("\nNo documents found in the database.")
            return

        for doc in documents:
            print(
                f"  ID={doc.id} | "
                f"User={doc.user_id} | "
                f"File={doc.filename}"
            )

        # -----------------------------------------------------
        # 3. Verify every PDF still exists
        # -----------------------------------------------------
        print("\nChecking PDF files...")

        missing_files = []

        for doc in documents:
            if not os.path.exists(doc.file_path):
                missing_files.append(
                    f"Document ID {doc.id}: {doc.file_path}"
                )

        if missing_files:
            print("\nERROR: The following PDF files are missing:")

            for path in missing_files:
                print(f"  - {path}")

            print(
                "\nMigration stopped. "
                "No existing Chroma data has been deleted."
            )
            return

        print("✓ All PDF files found.")

        # -----------------------------------------------------
        # 4. Close database session before rebuilding
        # -----------------------------------------------------
        db.close()
        db = None

        # -----------------------------------------------------
        # 5. Remove old Chroma database
        # -----------------------------------------------------
        print("\nRemoving old Chroma database...")

        if os.path.exists(settings.CHROMA_DB_DIR):
            shutil.rmtree(settings.CHROMA_DB_DIR)

        os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)

        print("✓ Old Chroma database removed.")
        print("✓ Fresh Chroma directory created.")

              # Import RAGService only AFTER the old Chroma database
        # has been deleted and the new directory has been created.
        from app.services.rag_service import RAGService

        # -----------------------------------------------------
        # 6. Create NEW RAG service
        # -----------------------------------------------------
        print("\nLoading new RAG service...")
        print("Embedding model:")
        print(f"  {settings.EMBEDDING_MODEL}")

        new_rag = RAGService()

        print("✓ New Chroma collection created.")

        # -----------------------------------------------------
        # 7. Re-index every existing PDF
        # -----------------------------------------------------
        print("\nRe-indexing documents...")
        print("-" * 70)

        successful = 0
        failed = 0
        total_chunks = 0

        for doc in documents:
            print(
                f"\nProcessing Document ID={doc.id}: "
                f"{doc.filename}"
            )

            try:
                chunk_count = new_rag.index_document(
                    doc_id=doc.id,
                    user_id=doc.user_id,
                    filename=doc.filename,
                    file_path=doc.file_path
                )

                total_chunks += chunk_count
                successful += 1

                print(
                    f"✓ Successfully indexed "
                    f"{chunk_count} chunks."
                )

            except Exception as e:
                failed += 1

                print(
                    f"✗ FAILED: {doc.filename}"
                )
                print(f"  Error: {e}")

        # -----------------------------------------------------
        # 8. Final verification
        # -----------------------------------------------------
        print("\n" + "=" * 70)
        print("MIGRATION COMPLETE")
        print("=" * 70)

        print(f"Documents in database : {len(documents)}")
        print(f"Successfully indexed   : {successful}")
        print(f"Failed                  : {failed}")
        print(f"Total new chunks        : {total_chunks}")

        # Check Chroma count
        try:
            count = new_rag.collection.count()
            print(f"Chroma vector count     : {count}")
        except Exception as e:
            print(f"Could not check Chroma count: {e}")

        if failed == 0:
            print("\n✓ All documents migrated successfully.")
            print("✓ MiniLM embeddings are now being used.")
            print(f"✓ Old Mistral backup remains at:")
            print(f"  {BACKUP_DIR}")
        else:
            print("\n⚠ Some documents failed to migrate.")
            print("Keep the Mistral backup until the problem is fixed.")

    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    main()