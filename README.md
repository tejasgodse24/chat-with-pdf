# Chat with PDF - Hybrid Inline + RAG System

A robust, event-driven chat system that allows users to upload PDF documents and chat with them using a hybrid approach: **inline processing** (base64 PDF) for immediate responses and **RAG (Retrieval Augmented Generation)** for fully indexed documents.

**Assignment:** CellStrat Backend Engineer (AI) Take-Home Challenge
**Duration:** 2 days
**Milestones Completed:** ✅ 1, 2, 3, 4 (All)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [API Endpoints](#api-endpoints)
- [Testing Guide](#testing-guide)
- [Milestones Completed](#milestones-completed)
- [Known Limitations](#known-limitations)
- [Assumptions](#assumptions)
- [Documentation](#documentation)

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **PostgreSQL** (or Neon Postgres)
- **AWS Account** (S3 bucket and Lambda configured)
- **OpenAI API Key**
- **Upstash Vector** account

### Installation

1. **Clone the repository:**
   ```bash
   cd chat_with_pdf
   ```

2. **Create virtual environment:**

   **On Windows:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   **On Mac/Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   The `.env` file is already provided with credentials. Ensure it contains:
   ```env
   # OpenAI
   OPENAI_API_KEY=your_openai_key

   # Database
   DATABASE_URL=postgresql://user:password@host/dbname

   # Upstash Vector
   UPSTASH_VECTOR_URL=your_upstash_url
   UPSTASH_VECTOR_TOKEN=your_upstash_token
   UPSTASH_VECTOR_NAMESPACE=swe-test-yourname

   # AWS
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=ap-south-1
   S3_BUCKET_NAME=swe-test-yourname-pdfs
   ```

5. **Set up the database:**

   Using Alembic:
   ```bash
   alembic upgrade head
   ```

6. **Run the server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`

7. **Configure AWS Lambda (for production):**

   - Lambda function: `swe-test-tejas-godse-ingest`
   - Set environment variable: `WEBHOOK_URL=https://ngrok-domain.com/webhook/ingest`
   - For local testing, use ngrok: `ngrok http 8000`

---

### Key Components

1. **FastAPI Backend**: RESTful API with routes for file upload, chat, and retrieval
2. **PostgreSQL Database**: Stores files, conversations, and messages
3. **AWS S3**: Object storage for PDF files
4. **AWS Lambda**: Event-driven ingestion trigger
5. **Upstash Vector**: Vector database for semantic search
6. **OpenAI API**:
   - `text-embedding-3-small` for embeddings
   - `gpt-4.1-mini` for chat completions

### Tech Stack

- **Backend Framework:** FastAPI + Pydantic
- **Database:** PostgreSQL with SQLAlchemy + Alembic
- **Vector Database:** Upstash Vector
- **Cloud Storage:** AWS S3
- **Compute:** AWS Lambda
- **AI/ML:** OpenAI SDK (no LangChain/LlamaIndex)
- **PDF Processing:** PyMuPDF (fitz)
- **Chunking:** tiktoken (512 tokens, 20% overlap)

---
## Postman Collection -  Import the provided Postman collection (`New Collection Copy.postman_collection.json` inside docs folder) for easier testing.

---


## Testing Guide

### End-to-End Flow

#### 1. Upload a PDF

**Step 1:** Get presigned URL
```bash
curl -X POST http://localhost:8000/presign \
  -H "Content-Type: application/json" \
  -d '{"filename": "travel-guide.pdf"}'
```

**Response:**
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "presigned_url": "https://s3.amazonaws.com/...",
  "expires_in_seconds": 3600
}
```

**Step 2:** Upload to S3
```bash
curl -X PUT "https://s3.amazonaws.com/..." \
  -H "Content-Type: application/pdf" \
  --data-binary @travel-guide.pdf
```

**Step 3:** Trigger ingestion - (Not Needed . Lmabda is configured for trigger)
```bash
curl -X POST http://localhost:8000/webhook/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "swe-test-yourname-pdfs",
    "s3_key": "uploads/550e8400-e29b-41d4-a716-446655440000.pdf"
  }'
```

#### 2. Test Inline Chat (Before Ingestion Completes or manually set ingestion_status="UPLOADED" in files databse) - (add conversation_id from response if you want to continue conversation)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is this document about?",
    "file_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Expected:** `retrieval_mode: "inline"` (PDF sent as base64)

#### 3. Wait for Ingestion to Complete (you can manually set ingestion_status="COMPLETED" in files databse)

```bash
curl http://localhost:8000/files/550e8400-e29b-41d4-a716-446655440000
```

Check: `ingestion_status: "completed"`

#### 4. Test RAG Mode (After Ingestion)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the best time to visit Starville?",
    "file_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Expected:** `retrieval_mode: "rag"` with `retrieved_chunks` array

#### 5. Test Retrieval Endpoint

```bash
curl -X POST http://localhost:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["550e8400-e29b-41d4-a716-446655440000"],
    "query": "transportation options",
    "top_k": 5
  }'
```

---

## Milestones Completed

### ✅ Milestone 1: File Upload & CRUD APIs (Complete)
- `/presign` endpoint with UUID generation and S3 presigned URLs
- `/webhook/ingest` endpoint for Lambda triggers
- `/files` and `/files/{file_id}` endpoints with pagination
- Database schema with SQLAlchemy and Alembic

---

### ✅ Milestone 2: Inline Chat with Base64 PDF (Complete)
- `/chat` endpoint with base64 PDF support (inline mode)
- `/chats` and `/chats/{conversation_id}` endpoints
- Multi-turn conversation support with history
- Context window patching with base64 PDFs

---

### ✅ Milestone 3: RAG Pipeline & Retrieval (Complete)
- Full ingestion pipeline:
  - PDF text extraction (PyMuPDF)
  - Manual chunking (512 tokens, 20% overlap with tiktoken)
  - Embedding generation (OpenAI `text-embedding-3-small`)
  - Vector storage in Upstash with metadata
- `/retrieve` endpoint for independent testing
- Metadata filtering by `file_id`

---

### ✅ Milestone 4: Dynamic Mode Switching with Tool Calling (Complete)
- Enhanced `/chat` with dynamic mode detection:
  - **Inline mode** (status="uploaded"): Base64 PDF sent to LLM
  - **RAG mode** (status="completed"): Semantic search via tool calling
- OpenAI tool calling manually implemented (no frameworks)
- System instruction to guide LLM tool usage
- Metadata filtering for multi-file conversations

---

## Known Limitations

### Technical Constraints and considerations or assumptions

1. **Single-User System**: No authentication or multi-tenancy implemented
2. **File Size Limit**: Maximum 50 MB per PDF and also taking recent files if combined size is gretaer than 50mb (OpenAI limit) -
3. **Context Window**: Last 20 messages only (to stay within token limits)
4. **PDF Format**: Text-based PDFs only (no OCR for scanned documents)
5. **No File Deduplication**: Same file uploaded twice creates separate records
6. **No Conversation Summarization**: Long conversations may exceed context limits
7. No rate limiting on OpenAI API calls
8. model used : gpt-4.1-mini 
9. Large PDFs may timeout or exceed token limits
10. Failed ingestions set status="failed" but don't auto-retry. Manual re-upload required for failed files


---

## Assumptions

### System Assumptions

1. **Network Reliability**: Assumes stable network for S3, OpenAI, and Upstash
2. **AWS Configuration**: S3 bucket and Lambda are pre-configured correctly
3. **Environment Variables**: All credentials are valid and have proper permissions
4. **Database Connection**: PostgreSQL is running and accessible

### User Behavior Assumptions

1. **File Format**: Users upload valid, text-based PDF files
2. **Single User**: Only one user interacts with the system at a time
3. **File Upload**: Users wait for presigned URL before uploading
4. **Conversation Flow**: Users don't rapidly spam requests

### Data Assumptions

1. **PDF Content**: PDFs contain extractable text (not scanned images)
2. **File Size**: PDFs are under 50 MB
3. **Text Quality**: Extracted text is readable and coherent
4. **Language**: PDFs are primarily in English (OpenAI models optimized for English)

### Operational Assumptions

1. **Ingestion Time**: Ingestion completes within 2 minutes for typical PDFs
2. **Lambda Execution**: Lambda successfully calls webhook endpoint
4. **Error Messages**: All errors are logged and visible in application logs

---

## Documentation

For detailed documentation, see:

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: System design, database schema, and key design decisions
- **[DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md)**: AI usage, prompting strategy, challenges, and learnings

---

## Project Structure

```
chat_with_pdf/
├── api/
│   ├── routes/              # FastAPI routers
│   │   ├── file_router.py
│   │   ├── webhook_router.py
│   │   ├── chat_router.py
│   │   └── retrieval_router.py
│   └── schemas/             # Pydantic models
│       ├── request.py
│       └── response.py
├── database/
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── file.py
│   │   ├── conversation.py
│   │   └── message.py
│   └── repositories/        # Data access layer
│       ├── file_repository.py
│       ├── conversation_repository.py
│       └── message_repository.py
├── services/
│   ├── file_service/
│   │   ├── s3_service.py           # S3 operations
│   │   ├── pdf_extraction_service.py
│   │   └── chunking_service.py
│   ├── vector_service/
│   │   ├── embeddings_service.py   # OpenAI embeddings
│   │   └── upstash_service.py      # Vector operations
│   └── chat_service/
│       ├── chat_handler.py         # Main chat logic
│       ├── context_builder.py      # Context window management
│       └── openai_service.py       # OpenAI API calls
├── core/
│   ├── exceptions.py        # Custom exception classes
│   └── utils/
│       ├── logger.py
│       └── helpers.py
├── alembic/                 # Database migrations
├── docs/
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT_LOG.md
|   └── New Collection Copy.postman_collection.json
├── config.py                # Pydantic settings
├── main.py                  # FastAPI app entry point
├── .env                     # Environment variables
├── requirements.txt
└── README.md
```
