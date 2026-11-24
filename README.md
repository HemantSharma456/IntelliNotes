# IntelliNotes — AI Academic Study Assistant MVP

IntelliNotes is a locally runnable, source-grounded AI academic study assistant inspired by Google's NotebookLM. It empowers students and researchers to upload academic materials (PDFs and lecture notes), ask concept questions with verifiable page-level citations, synthesize comprehensive study notes, take interactive practice quizzes, and prepare for oral exams / viva voce.

---

## 🌟 Key Features

1. **Document-Grounded RAG (Retrieval-Augmented Generation)**:
   - Chunking with sliding windows and paragraph boundary awareness.
   - Vector indexing powered by `sentence-transformers` (`all-MiniLM-L6-v2`) and `FAISS`.
   - Strict source citations with document names, page numbers, similarity scores, and expandable text excerpts.
   - Refusal & safety heuristics for out-of-scope questions.

2. **Full-Featured Study Tools**:
   - **Executive Summaries**: High-yield takeaways and key concepts.
   - **Interactive Practice MCQs**: Auto-generated questions with multiple options, instant grading, and in-depth rationales.
   - **Interactive 3D Flashcards**: Flip-card animation for rapid active recall and spaced repetition.
   - **Viva Voce Prep**: Probing oral exam questions categorized by concept depth (Core Theory, Implementation, Edge Cases) with model answers.

3. **Modern, Responsive User Interface**:
   - Built with React, TypeScript, and Tailwind CSS.
   - Dark mode aesthetics, glassmorphism, micro-animations, and responsive drawer navigation.

---

## 🏗️ Architecture

```
Project_Imd/
├── backend/
│   ├── app/
│   │   ├── api/routes.py         # REST endpoints for health, documents, chat, study tools
│   │   ├── models/schemas.py     # Pydantic v2 schemas and validation
│   │   ├── services/
│   │   │   ├── chunking.py       # Sliding-window document chunking
│   │   │   ├── documents.py      # PDF (PyMuPDF) and TXT extraction & sanitization
│   │   │   ├── embeddings.py     # Sentence-transformers and FAISS vector index
│   │   │   ├── llm.py            # Google Gemini 2.0 Flash integration
│   │   │   ├── rag.py            # Retrieval-Augmented Generation pipeline
│   │   │   ├── retrieval.py      # Top-K semantic search and similarity scoring
│   │   │   ├── store.py          # SQLite persistence for documents and chunks
│   │   │   └── study.py          # Study tools logic (Summaries, MCQs, Flashcards, Viva)
│   │   ├── config.py             # App settings loaded from .env
│   │   └── main.py               # FastAPI application setup and lifespan
│   ├── evaluation/               # RAG evaluation scripts and dataset
│   ├── tests/                    # Pytest test suite
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Sidebar.tsx        # Document upload, selection, and deletion
    │   │   ├── ChatView.tsx       # Q&A view with streaming markdown & citations
    │   │   ├── CitationCard.tsx   # Expandable citations with page & score
    │   │   └── StudyToolsView.tsx # Summary, MCQs, 3D Flashcards, and Viva Prep
    │   ├── services/api.ts        # Typed API service client
    │   ├── types/index.ts         # TypeScript interfaces
    │   ├── App.tsx                # Main view and navigation
    │   └── styles.css             # Tailwind theme & animation definitions
    └── package.json
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** and **npm**
- **Google Gemini API Key** ([Get one here](https://aistudio.google.com/))

---

### 2. Backend Setup

1. Open a terminal in the `backend/` directory:
   ```powershell
   cd backend
   ```

2. (Optional) Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install required packages:
   ```powershell
   pip install -r requirements.txt
   ```

4. Create your `.env` configuration file:
   ```powershell
   copy .env.example .env
   ```
   Open `.env` and set your `GEMINI_API_KEY`:
   ```env
   GEMINI_API_KEY=AIzaSy...your_actual_api_key_here
   GEMINI_MODEL=gemini-2.0-flash
   ```

5. Start the backend server:
   ```powershell
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   *The interactive API documentation will be available at `http://127.0.0.1:8000/docs`.*

---

### 3. Frontend Setup

1. Open a new terminal in the `frontend/` directory:
   ```powershell
   cd frontend
   ```

2. Install dependencies (if not already installed):
   ```powershell
   npm install
   ```

3. Start the development server:
   ```powershell
   npm run dev
   ```
   Open your browser and navigate to `http://localhost:5173`.

---

## 🧪 Running Tests & Evaluation

### Backend Unit & Integration Tests
Run pytest from the repository root or backend folder:
```powershell
python -m pytest backend/tests -v
```

### RAG Evaluation Benchmark
Run the evaluation script to test retrieval recall, citation validity, and latency:
```powershell
python backend/evaluation/evaluate.py
```

---

## 🛡️ License
MIT License. Created for academic study and research assistance.
