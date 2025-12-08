# Architecture Documentation

## System Architecture Diagram

### System Architecture Diagrams are included in docs folder itself. i have used excalidraw for this. this is actual url for the same.
 [https://excalidraw.com/#json=24F-oahskWGKjYxIP_zWF,Jz0IEDZXnafTTKP1LVV8nw]

<br><br>

## Database Schema

### 1. separate tables for conversation, meesage and file , following db normalization rules . 
### 2. no data duplicassy, and simle to understand and intuitive
### 3. conversation centric structure , can easily track and get chats from one conversation and files related to it
### 4. JSONB for retrieved_chunks : in future if chunk schema changed then it will be easy to store as json . if we create another table, then will take time at insertion. 
### 5. UUIDs  as PK : Globally unique. no integer overflow error

---


<br><br>


## Apply all migrations (creates tables)
```alembic upgrade head```

---

<br><br>

## Chunking Strategy

### Chunk Size: 512 tokens
### Overlap: 20% (approximately 102 tokens)
### Tokenizer: tiktoken (text-embedding-3-small)

---
### OpenAI embeddings have token limits (8191 for text-embedding-3-small)
### Fixed size ensures no chunk exceeds limits
### Simplicity and No LangChain/LlamaIndex requirement
### GPT-4 can easily process 512-token chunks
### Multiple chunks (5-10) fit comfortably in context
### Simple to implement - No complex NLP

### Overlap
1. Important sentences near boundaries appear in 2 chunks
2. Increases chance of matching user queries
3. Redundancy helps with ambiguous queries
4. 10% overlap: Too small, still misses context
5. 20% overlap: Sweet spot (102 tokens = ~2-3 sentences)
6. 50% overlap: Excessive redundancy, storage wastes


<br><br>

## COntext window management

### 1. Max File Size: 50 MB
* OpenAI API limit for base64-encoded files in messages

### 2. Max Messages: Last 20 message
* Keeps context window manageable
* GPT-4.1-mini context window: 128K tokens
* Reserved for: conversation history + files + retrieved chunks

### 2. kepp recent files 
* if combined file size is greater than 5 mb , then we will take recent files and leave last ones. 
* we will do this only for inline files, means files having status="completed"
 
### 3. Mode-Specific Context Building

### Inline Mode (status = uploaded)
  * Download selected files from S3
  * Encode to base64
  * Patch into first user message as image content
  * Include last 20 messages
  * Total size must be < 50 MB

### RAG Mode (status = completed)
* No file downloads (uses vector search instead)
* Include last 20 messages
* Inject historical RAG chunks as system messages
* Add newly retrieved chunks after tool call
* Significantly smaller context (no base64 files)

### 4.Historical RAG Chunks and messages Injection
* get all messages from specific conversation. 
* with that , i will get all files connected to that messages.
* so check if that file's status 
* for files having status == "uploaded", we will get all files at start, download them, convert to base64 and will add in first message itself.  ang then add other messages  
* so it means all related context st start itself. 
* for files having status == "completed", we will add "tool" with the message.
* then again check response if it is a tool call, if yes then call our function to get related chunks from upstash and again send all the chunks and with all message history to openai api , and then get response as RAG.

### 5. Optimization Techniques and others

* Track seen files by file_id, Prevent duplicate file inclusions, Reduces context size
* we are adding one file only once , not repeat same file again and again
* Only download files needed for inline mode, Skip downloads for RAG files (use vector search), Reduces S3 API calls and bandwidth
* Single query for messages + files


<br><br>


## Error Handling
* Log full error details server-side for debugging
* retry logic is not implemented . 
* Invalid File Format : error handling done 
* File Size Validation
* Custom exceptions for domain-specific errors
* Try-except blocks in all service functions
* Logging before raising exceptions
* Generic fallback for unexpected errors (500)


### HTTP Status Codes
* 400: Bad request (invalid input, validation errors)
* 404: Resource not found (conversation, file)
* 409: Conflict (duplicate file)
* 413: Payload too large (file size exceeded)
* 422: Validation error (Pydantic)
* 429: Rate limit exceeded
* 500: Internal server error (unexpected errors)
* 503: Service unavailable (external API down)
* Store detailed error_message for debugging



<br><br>



## Known Limitations
* No user authentication - Single-user system, no multi-tenancy
* No rate limiting - API can be overused
* Synchronous chat endpoint - Blocks during LLM calls, no streaming
* No retry logic - External API failures not automatically retried
* 50 MB file size limit - OpenAI API constraint for base64 encoding
* No caching - Repeated queries regenerate embeddings and responses
* Manual chunking only - No semantic/paragraph-aware chunking
* Single namespace in Upstash - All vectors in one namespace
* No file deletion - Once uploaded, files cannot be removed
* No conversation deletion - Conversations persist indefinitely
* Last 20 messages only - Older context not included
* No file format validation beyond extension - Relies on .pdf extension check
* No webhook authentication - Lambda webhook endpoint is public
* No monitoring/metrics - No built-in observability tools
* PostgreSQL only - No support for other databases


<br><br>


## Known Limitations
* Retry Logic with Exponential Backoff - Handle transient failures gracefully
* Advanced Chunking - Semantic chunking, paragraph-aware splitting
* Caching Layer - for donwloaded files
* Re-ranking - Use cross-encoder for better chunk selection
* Async Processing - Background tasks with Celery/RQ for ingestion
* Batch Embedding Generation - Process multiple chunks in parallel