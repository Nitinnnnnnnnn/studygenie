# 🧞‍♂️ StudyGenie: AI Academic Tutor & Quiz Prep Platform
### *Medium-Level Full-Stack GenAI Application (RAG + Mistral AI)*

[![React](https://img.shields.io/badge/Frontend-React_18_%2B_Tailwind-61DAFB?logo=react&logoColor=black)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_%2F_SQLite-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![ChromaDB](https://img.shields.io/badge/Vector_Store-ChromaDB-FF6F00)](https://www.trychroma.com/)
[![Mistral AI](https://img.shields.io/badge/LLM_%26_Embeddings-Mistral_AI-FF7000)](https://mistral.ai/)

---

## 📌 Project Overview
**StudyGenie** is a complete, production-ready full-stack educational assistant that transforms static course materials (PDF notes, syllabus, textbooks, research papers) into an active, personalized learning experience.

Unlike toy "Chat with PDF" tutorials, StudyGenie implements:
1. **Multi-Document Ingestion & RAG (Retrieval-Augmented Generation)** with page-level source citations and an interactive source inspection drawer.
2. **AI Interactive Quiz Engine** that generates grounded Multiple-Choice Questions (MCQs) across **3 difficulty levels (Easy / Medium / Hard)** and **5 / 10 / 20 question counts**, with real-time score grading and detailed explanations for every option.
3. **Enterprise-Grade Architecture**: PostgreSQL relational database via SQLAlchemy, ChromaDB vector store, JWT token authentication, and a modern React.js frontend.

---

## 🏛️ System Architecture

```
                                  STUDYGENIE ARCHITECTURE
                                  
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                           REACT.JS FRONTEND (Vite)                          │
  │  - JWT Login & Registration         - Document Manager (Multi-PDF Upload)   │
  │  - RAG Chat with Citation Drawer    - Interactive Quiz Runner & Explanations│
  │  - Quiz History & Score Dashboard   - Tailwind CSS + Lucide Icons           │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │ REST API (Bearer JWT Auth)
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                             FASTAPI BACKEND                                 │
  │  - /api/auth      : Register, Login, Current User                           │
  │  - /api/documents : Multi-PDF upload, chunking, deletion & sync             │
  │  - /api/chat      : Session management, RAG retrieval & source citing       │
  │  - /api/quiz      : Dynamic MCQ generation, submission scoring & review     │
  └──────────────┬───────────────────────────────────────────────┬──────────────┘
                 │                                               │
                 ▼                                               ▼
  ┌──────────────────────────────┐                ┌─────────────────────────────┐
  │   POSTGRESQL / SQLITE DB     │                │     CHROMADB VECTOR STORE   │
  │  - Users, Documents          │                │  - Chunks + Page Metadata   │
  │  - Chat Sessions & Messages  │                │  - Document ID partitioning │
  │  - Quizzes, Attempts, Answers│                │  - Mistral Embedding-based  │
  └──────────────────────────────┘                └──────────────┬──────────────┘
                                                                 │
                                                                 ▼
                                                  ┌─────────────────────────────┐
                                                  │       MISTRAL AI API        │
                                                  │  - mistral-embed            │
                                                  │  - mistral-small-latest     │
                                                  └─────────────────────────────┘
```

---

## ⚙️ Tech Stack Breakdown

| Layer | Technology | Why This Choice? |
| :--- | :--- | :--- |
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide Icons, Axios | Lightning fast build, responsive UI, component state management. |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic | High performance async REST APIs, automatic OpenAPI docs at `/docs`. |
| **Relational DB** | PostgreSQL / SQLite with SQLAlchemy ORM | Clean relational schema for users, documents, messages, and quiz attempts. |
| **Vector DB** | ChromaDB | Persistent local vector storage with cosine similarity indexing. |
| **Embeddings** | `mistral-embed` (1024 dimensions) | High-accuracy semantic embedding vectors for academic text. |
| **Generative LLM** | `mistral-small-latest` | Fast, cost-efficient, adheres strictly to system prompts and JSON schemas. |
| **Security** | JWT (JSON Web Tokens) & Passlib (Bcrypt) | Secure password hashing, stateless token-based authorization. |

---

## ✨ Core Features

### 1. 🔐 JWT-Based Authentication & User Isolation
* Secure registration and login with encrypted password storage.
* Multi-tenant data isolation: Each user only sees their own documents, chat sessions, and quiz scores.

### 2. 📂 Multi-PDF Document Management & ChromaDB Sync
* Upload multiple PDFs simultaneously with drag-and-drop.
* Extracts text per page using `pypdf` and creates 700-character overlapping chunks with metadata (`doc_id`, `filename`, `page_number`).
* **Clean Deletion**: Deleting a document removes its file from disk, its record from PostgreSQL, and deletes all its vector embeddings from ChromaDB.

### 3. 💬 RAG Q&A with Interactive Citation Inspector
* Ask questions across all notes or filter to a single document.
* Retrieves top-4 semantic chunks using cosine distance.
* Generates grounded responses with formatted citations `[Doc: Notes.pdf, Page 3]`.
* Clicking a citation badge opens the **Source Inspector Drawer**, showing the exact raw passage retrieved from ChromaDB with its similarity match percentage.

### 4. 🎯 AI Interactive Quiz Engine (Easy / Medium / Hard)
* **Custom Configuration**: Select document, difficulty (**Easy / Medium / Hard**), and question count (**5 / 10 / 20 questions**).
* Uses strict JSON Schema generation with Mistral to create plausible 4-option MCQs.
* **Live Quiz Runner**: Interactive carousel with timer and answer selection.
* **Instant Grading & Review**:
  * Final score and percentage rating ($A+, A, B$).
  * Green highlights for correct answers, Red for incorrect selections.
  * Comprehensive educational **Answer Explanations** for every question.
* **Past Attempt History**: Tracks scores over time.

---

## 🚀 Step-by-Step Setup & Installation

### Prerequisites
- Python 3.10 or higher
- Node.js 18+ and npm
- A free Mistral AI API key from [console.mistral.ai](https://console.mistral.ai/)

---

### Step 1: Clone & Setup Backend

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate a Python virtual environment
python -m venv venv

# On Windows (PowerShell):
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install required Python packages
pip install -r requirements.txt

# 4. Configure environment variables in .env
# Edit backend/.env and add your Mistral API key:
MISTRAL_API_KEY=your_mistral_api_key_here

# 5. Launch the FastAPI server
python run.py
```
> The backend server will start at **`http://localhost:8000`**.  
> Explore interactive Swagger API documentation at **`http://localhost:8000/docs`**.

---

### Step 2: Setup & Launch Frontend

Open a new terminal window:

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Start the Vite React development server
npm run dev
```
> The React web app will open at **`http://localhost:3000`** (or `http://localhost:5173`).


## 📜 License
This project is open-source and built for educational and portfolio demonstration purposes.
