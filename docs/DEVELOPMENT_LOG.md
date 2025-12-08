

### AI Tools & Models Used

## claude code, windsurf, chatgpt
## models used - claude sonnet 4.5 every where instead chatGPT

* claude code - used for heavy and complex implementaio of code. 
* short tasks - windsurf i prefer
* and research , doubt solving. 
* for architecture planning - i have used mostly claude code and windsurf in planning mode. 

<br><br>


## Prompting Workflow (Per Milestone)

### Milestone 1 

### Phase 1: Planning (~3 hours)
* first of all, put given doc in a folder and started with windsurf to understand what i have to do exactly 
* spent much more time in understanding the doc and requiremtns.
* first started with selceting python version adn dependancies i will require and accoding selecting versions for them. 
* then finalize folder structure with certain revlutions of prompts with windsurd. 
* so for a mile stone , i have again created small implementable tasks using claude code. 

### Phase 2:  Implementation (~3 hours)
* created s3 and lambda function. 
* reietrate if anything is going out of score . moved with checking the code and implementation, line by line. and then only move to the next task.
* started with task 1 in claude code to create models. 
* then implemented alembic migrations.
* then implemeneted repositories, service layers , scemas and finally api routeres

### Phase 3 Testing & Debugging (~1 hours)
* S3 bucket creation: No issues
* Lambda creation: Permission errors → Fixed with correct IAM policies
* Empty chunks: Some PDFs had no extractable text → Added validation



### Milestone 2 



### Phase 1: Planning (~3 hours)
* i  have implemented rag before but not from scratch but by using some libraries. 
* so first researched about Inline mode of openai models using chatgpt and docs of open ai as well.
* gone through docs of openai , for better understanding.
* also discussed multiple approach ith claude and windsurf ,  how  context management will going to work. 


### Phase 2:  Implementation (~3 hours)

* created services for the same like convert_to_64 and donwloadn_from_s3 etc using claude code. and also for open ai chat servie
* i got stuck at newer version of openai sdk between slient.respones and client.collections. it took my some time to reitarate and go through docs. 
* claude code given me old way of doing it , even after giving docs link forreference. 
* i had to implement basic context management . researched about it and dicided to go with the current one approach,  keeping time and scope in mind.  
* context management also took some iterations to work. at first respone handling was not correct so getting errross but resolved later
* and later the apis were remiing , crud functions was already their , so added routers and repositories using windsurf. 

### Phase 3 Testing & Debugging (~1 hours)
* tested it with multple file size and how much time it takes .
* got some errrors related to openai specifically meanwhile but resolved it using claude code , and debugging and logging .
* added exceptions and error handling 

### Milestone 3

### Phase 1: Planning (~ 2 hours)
* research about upstash, embeddings, and how can i fit that into my application.
* researched about pdf libs , which to use.  stucj at this point for some time , which to use . but got comparison from windsurf andmoved with one of them .
* finalize high level design for ingestion adn retrieval pipeline. 


### Phase 2:  Implementation (~2 hours)
* started with chunking and extracting text from pdf using claude code. 
* created all services related to ingestion using claude code itslef. which includes extract_text from pdf, chunk in 512 size, get tokens , embedd them using embedding servies and finalyy push into upstash. 
* develop retrieve api endpoint using same ,  

### Phase 3 Testing & Debugging (~0.5 hours)
* Tested connection with Upstash Vector using test vectors
* Verified namespace creation and vector storage
* Checked metadata filtering works correctly
* Metadata filter format was wrong (needed exact string match) - Fixed by checking Upstash docs



### Milestone 4

### Phase 1: Planning (~ 2 hours)
* Asked AI: "Explain OpenAI function calling / tool calling"
* gone through docs first.
* Discussed: When to use inline vs RAG mode
* Planned hybrid mode switching logic 


### Phase 2:  Implementation (~2 hours)
* here again changing chat api. 
* but before this, had to change context managemetn now . using claude coed. explaining him what i have diciede giveing proper well structured prompt. 
* some promptings are like
* "Implement file categorization by ingestion_status"
* "Create OpenAI tool definition for semantic_search" but more descriptive one
* "Add historical RAG chunk injection"
* "Update context builder for hybrid mode"

### Phase 3 Testing & Debugging (~0.5 hours)
* Tool Definition Format -needed some iterations to get it done
* Had to repeatedly tell AI: "No LangChain"
* Tool description needed examples to guide LLM
* Retrieval mode tracking was tricky
* Historical chunks must maintain conversation flow
* Tool Not Being Called: 
* current added file id was not getting into rag mode , even if everything was right. 
* later i discoverd the logic was not correct which llm was missing over iterations. i resolved it myself.

<br><br>

###  AI Usage Philosophy

as i said earlier , i used both plan adn implementation mode . but i never give prompts which are too general , means refering high level desing to build or write donw code. this creates a mess. 

first i discuss with model the low level code as well and then jump to implementation. 

Historical chunks order was incorrect (chunks before assistant message)
File download optimization (AI downloaded all files, I filtered early)
AI used integer IDs → I enforced UUIDs. AI may give outdated/wrong API formats

OpenAI Tool Format: AI gave Chat Completions API format (nested structure) then i manually Referenced official Responses API docs

Flow whcih works for me : 
Plan mode → Understand requirements, design architecture
Break into tasks
Direct implementation → Write code task by task
Test → Debug → Iterate


<br><br>
### Key Prompting Insights

#### 1. Don't Assume AI Remembers Everything
When implementing Milestone 4, I asked AI to "update the chat handler for RAG mode." It gave me code that completely ignored the inline mode logic I'd built earlier. I started providing explicit context: "I have inline mode working (base64 PDFs). Now add RAG mode that checks ingestion_status. If 'completed', use tool calling. If 'uploaded', use existing inline logic."

#### 2. Official Docs - Verify External APIs
spent 2 hours debugging OpenAI tool calling. AI kept giving me the Chat Completions API format (nested function object), but I was using Responses API. Error: "Missing required parameter: tools[0].name"

**What I Did:**  
Stopped asking AI, went directly to OpenAI docs. Found the correct format needs "type": "function" at top level, not nested. Showed AI the docs link and said "use THIS exact format."

#### 3. Break Complex Tasks Into Tiny Steps
Avoid "Build Everything" Prompts  
i always prefer to break tasks into low level understanding and planning and then only implement tasks one by one at a time.

#### 4. Debugging Prompts Need Full System Context Not Just Error Messages
**Situation:** Vector search returned empty results. I asked: "Why is Upstash returning no results?"  
AI suggested generic things like "check if vectors exist" or "verify embeddings."

**What Worked Better:**  
Shared the full picture: "I'm querying Upstash with metadata filter file_id = 'uuid'. Vectors were upserted with metadata {'file_id': 'uuid'}. Query embedding is 1536-dim. Getting 0 results but vectors exist."

**AI's Response:**  
"The filter syntax might be wrong. Upstash expects string format. Try wrapping UUID in quotes: file_id = 'uuid-string'"

**Result:** That was exactly the issue - metadata filter format.

**Takeaway:**  
Don't just paste error messages. Describe: what you're trying to do, what you expect, what's actually happening, and relevant code/config. AI needs the full system picture to debug effectively.


---

### Implementation Challenges & Solutions

#### 1. Historical RAG Chunks Breaking Message Order
**Problem:**  
When injecting historical RAG chunks into context, chunks appeared before assistant message, making conversation flow illogical. OpenAI confused about who said what.

**Root Cause:**  
AI's initial implementation added chunks first, then assistant message.

**Solution:**
- Refactored to always add assistant message **FIRST**
- Then append chunks as system message **AFTER**
- Correct flow: User → Assistant → \[System: chunks used\] → User → ...
- Also fixed JSONB handling (AI suggested json.loads() but SQLAlchemy auto-deserializes)
- Iterations: 3 attempts to get order and format correct


#### 2. Tool Calling Not Persistent Across Conversation
**Problem:**  
Tool only triggered when current message had a file attached. If file was uploaded in message 1, asking a question in message 5 (without file) didn't trigger tool call, even though file was completed and indexed.

**Root Cause:**  
Logic checked if new_file_id and file.status == 'completed' — only looked at current message, not conversation history.

**Solution:**
- Changed logic to check entire conversation state: **if len(rag_file_ids) > 0**
- Tool now available for ANY message if conversation has completed files
- AI kept missing this — I had to think through conversation state myself

**Learning:**  
AI thinks per-request, not per-conversation. Must explicitly handle state.


#### 3. Inefficient File Downloads for RAG Files
**Problem:**  
Context builder downloaded ALL files from S3, including RAG-mode files (which don't need download since we use vector search). Wasted bandwidth and S3 API calls.

**Root Cause:**  
AI's initial implementation: "collect all files → download all files → filter later"

**Solution:**
- Modified collect_all_files_from_conversation() to accept inline_file_ids filter
- Only download files in inline_file_ids list
- Skip RAG files entirely (handled via vector search)
- Added early filtering before S3 calls

**Impact:** Reduced S3 downloads by ~50% in typical RAG conversations.


#### 5. Upstash Metadata Filter Format Issues
**Problem:**  
Vector search returned 0 results even though vectors existed. Query was correct, embeddings were correct, but filtering by file_id failed silently.

**Root Cause:**  
Metadata filter syntax was wrong. Used Python dict format instead of Upstash string format.

**Solution:**
- Read Upstash Vector documentation
- Changed from dict to string: `file_id = 'uuid-string'`
- For multiple files: `file_id IN ('uuid1', 'uuid2')`
- AI didn't know Upstash-specific syntax — had to check docs

**Debugging Approach:**
- Tested without filter (worked)
- Tested with filter (failed)
- Checked Upstash docs for exact filter syntax
- Fixed format manually

---

### TOTAL  
**~23.5 hours over 2 days**

### What Worked Well

AI Usage
* Planning mode first (Windsurf/Claude) - Discussing architecture before coding saved rework time
* Breaking tasks into small functions - One function per prompt = cleaner, testable code
* Claude Code for complex refactoring - Multi-file changes handled well (Milestone 4)
* Using multiple AI tools - Claude for heavy tasks, Windsurf for quick fixes/planning research, ChatGPT for research

Development Process
* Milestone-based approach - Clear deliverables kept me focused and organized
* Testing incrementally - Caught bugs early, didn't wait until everything was done
* Extensive logging - Made debugging much easier, could trace execution flow
* Reading official docs - Saved hours on OpenAI, Upstash, AWS API issues

Tools & Workflow
* Postman for API testing - Quick iteration, saved collections for reuse
* Repository pattern - Clean separation made changes easier
* SQLAlchemy eager loading - Prevented N+1 queries from the start



## What I'd Improve

Planning & Design
* Should have drawn diagrams on paper first - Jumped into AI prompting too quickly sometimes
* Should have documented decisions earlier - Wrote docs at the end, should have done it alongside
* Should have planned error handling upfront - Added it later, should be part of initial design

Development Practices
* More frequent commits - Did ~8 commits, should be 15-20+ (one per feature/fix)
* Should have written tests - No unit tests, debugging took longer as a result
* Should have used Docker - Would make deployment and testing easier
* Better git messages - Some commits were vague, should be more descriptive

AI Usage
* Should have used plan mode more consistently - Sometimes jumped straight to implementation
* Should have verified AI code immediately - A few times trusted AI, found bugs later
* Should have asked for smaller changes - Some prompts were too broad, got messy code

Time Management
* Milestone 4 took too long - Should have broken it down more, 12 hours was too much in one go
* Should have taken breaks - Long debugging sessions were less productive
* Should have researched APIs earlier - Spent 2 hours on OpenAI format that docs would have solved in 10 minutes


### Key Learnings

1.  AI as Junior Developer
2. Plan Mode > Direct Implementation
3. Simple and clear is Better
4. Error Handling Matters
5. Break Down Problems
6. Documentation is Important
7. Testing Saves Time


### What I'd Do Differently Next Time

Before Starting
* Draw system architecture on paper - Visual understanding before prompting
* Set up Docker and testing framework - Infrastructure first
* Create detailed task breakdown - More granular than milestones
* Research all external APIs - Read docs before asking AI

During Development
* Commit after every working feature - Better git history
* Write tests alongside code - TDD or at least test-driven
* Use plan mode consistently - Don't skip planning phase
* Document decisions immediately - Don't wait until end

AI Interaction
* Smaller, more focused prompts - One function at a time
* Always verify with docs - Especially for external APIs
* Provide full context - Don't assume AI remembers
* Review code immediately - Don't accumulate unreviewed code