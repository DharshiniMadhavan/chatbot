# RAG Project Q&A Documentation

This document answers every topic from the image in the requested format, using this specific LangChain HR Policy RAG project as the reference.

Project references:

- `langchain/rag_langchain.py`: RAG pipeline, PDF parsing, chunking, embeddings, Pinecone, Gemini, PostgreSQL memory.
- `langchain/app.py`: FastAPI backend.
- `langchainfrontend/chat-ui/src/App.js`: React frontend.
- `langchain/.env`: model, index, and API configuration.
- `langchain/HRPolicy.pdf`: source document.

## Architecture Overview

This project is a Retrieval Augmented Generation chatbot for HR policy questions. React sends a question to FastAPI. FastAPI calls a LangChain chain. LangChain retrieves relevant chunks from Pinecone and sends them with the question and chat history to Gemini. PostgreSQL stores conversation history per `session_id`.

Backend API routes:

- `POST /chat`: receives `session_id` and `question`, returns `answer`.
- `POST /new-chat`: creates a new chat session ID.
- `GET /history?session_id=...`: returns previous messages for that session.

Main RAG flow:

1. `PyPDFLoader` loads `HRPolicy.pdf`.
2. `RecursiveCharacterTextSplitter` splits pages into chunks.
3. `GoogleGenerativeAIEmbeddings` creates vectors.
4. `PineconeVectorStore` stores and retrieves vectors.
5. `ChatPromptTemplate` builds the final prompt.
6. `ChatGoogleGenerativeAI` calls Gemini for the answer.
7. `RunnableWithMessageHistory` connects the chain to PostgreSQL chat memory.

---

## 1. Content Parsing

> **Area:** *Content Parsing*
>
> **What to Research:** *How documents are converted into clean text before chunking.*
>
> **Questions You Must Answer:**
>
> - How do we parse PDF, HTML, PowerPoint, Excel, and Word documents?
> - What issues occur with tables, headers, footers, images, and scanned documents?

### Q: How do we parse PDF, HTML, PowerPoint, Excel, and Word documents?

In this project, only PDF parsing is implemented. The HR document is `langchain/HRPolicy.pdf`, and the parsing happens in `load_pdf()` in `langchain/rag_langchain.py`:

```python
def load_pdf():
    loader = PyPDFLoader(PDF_PATH)
    return loader.load()
```

`PyPDFLoader` converts the PDF into LangChain `Document` objects. Each object contains extracted text in `page_content` and metadata such as source and page details where available.

HTML, PowerPoint, Excel, and Word parsing are not implemented in this project. If needed, the same architecture can be extended with different loaders:

- HTML: `WebBaseLoader`, `BSHTMLLoader`, or BeautifulSoup-based parsing.
- PowerPoint: Unstructured PowerPoint loader.
- Excel: Pandas or an Excel loader that converts rows and sheets into text.
- Word: `Docx2txtLoader` or an Unstructured Word loader.

The goal is always to normalize different source formats into LangChain `Document` objects, because the later stages of the project expect documents that can be chunked, embedded, stored in Pinecone, and retrieved.

### Q: What issues occur with tables, headers, footers, images, and scanned documents?

Tables may lose row and column structure when extracted as plain text. This can damage HR policy meaning, especially when leave limits, eligibility, or notice period rules are written in table format.

Headers and footers may repeat on every page. If repeated text appears in every chunk, embeddings become noisy and retrieval quality decreases.

Images are usually ignored by normal text extraction. If a policy rule appears inside an image, diagram, signature block, or scanned notice, `PyPDFLoader` may not capture it.

Scanned documents are often image-only PDFs. They need OCR before parsing. The current project assumes `HRPolicy.pdf` has selectable/extractable text. For production, OCR and table-aware parsing would be important improvements.

---

## 2. Content Structure

> **Area:** *Content Structure*
>
> **What to Research:** *How source content should be organized before indexing.*
>
> **Questions You Must Answer:**
>
> - Should we store page number, section title, document type, author, version, date, and business domain? Why?

### Q: Should we store page number, section title, document type, author, version, date, and business domain? Why?

Yes. The current project mainly relies on default metadata from `PyPDFLoader` and LangChain splitting. That is enough for a proof of concept, but a production HR policy chatbot should store richer metadata.

Recommended metadata:

```json
{
  "doc_id": "hr_policy",
  "chunk_id": "hr_policy_0001",
  "page_no": 5,
  "section": "Leave Policy",
  "document_type": "HR Policy",
  "author": "HR Department",
  "version": "v1",
  "created_date": "2026-07-07",
  "business_domain": "HR",
  "source_file": "HRPolicy.pdf"
}
```

Page number helps with citations. Section title helps explain where the answer came from. Document type separates policy documents from FAQs or forms. Author helps identify whether the content is official. Version and date prevent outdated policy answers. Business domain lets the retriever search only HR content when the system grows.

In the current code, `format_docs()` only sends `doc.page_content` to Gemini, so citations are not shown yet. Adding metadata to the prompt and API response would make answers more trustworthy.

---

## 3. Chunking Strategy

> **Area:** *Chunking Strategy*
>
> **What to Research:** *Fixed-size, recursive, semantic, page-based, section-based, and parent-child chunking.*
>
> **Questions You Must Answer:**
>
> - Why did we choose this chunking strategy?
> - What happens if chunks are too small or too large?
> - How do overlap and boundaries affect answer quality?

### Q: Why did we choose this chunking strategy?

The project uses recursive character chunking:

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50
)
```

This strategy is simple, reliable, and built into LangChain. It works well for a text-heavy HR policy PDF because it tries to split on natural boundaries before falling back to character-level splitting.

It is used because embedding entire pages or the full PDF would make retrieval less precise. Smaller chunks allow Pinecone to return only the most relevant policy text.

### Q: What happens if chunks are too small or too large?

If chunks are too small, important context may be split apart. For example, eligibility may be in one chunk and the actual number of leave days in another. The model may receive incomplete context.

If chunks are too large, each vector may represent multiple unrelated policy topics. Retrieval becomes less precise, and the final prompt may contain unnecessary text, increasing token usage.

In this project, `chunk_size=300` keeps chunks focused. A future improvement could use section-based chunking so each chunk follows HR policy headings.

### Q: How do overlap and boundaries affect answer quality?

Overlap protects information near chunk edges. This project uses `chunk_overlap=50`, so some text is repeated between neighboring chunks. This helps prevent important sentences from being cut in half.

Boundaries matter because chunks should represent meaningful units. Recursive character boundaries are acceptable for the proof of concept. Section boundaries would be better for HR policy documents because policy rules are often organized by headings.

---

## 4. Embedding Model

> **Area:** *Embedding Model*
>
> **What to Research:** *OpenAI, BGE, E5, Cohere, Gemini, Azure, and local models.*
>
> **Questions You Must Answer:**
>
> - Why choose one embedding model over another?
> - Compare accuracy, language support, cost, speed, dimension, and deployment option.
> - OpenAI's current embedding docs mention 1536 dimensions for `text-embedding-3-small` and 3072 for `text-embedding-3-large`, with optional dimension reduction.

### Q: Why choose one embedding model over another?

Embedding models are chosen based on retrieval quality, cost, speed, language support, vector dimension, and deployment requirements.

This project uses Gemini embeddings:

```python
GoogleGenerativeAIEmbeddings(
    model=f"models/{EMBED_MODEL}" if not EMBED_MODEL.startswith("models/") else EMBED_MODEL,
    client_args=get_google_client_args(),
)
```

The `.env` file sets:

```env
EMBED_MODEL = "gemini-embedding-001"
```

Gemini is used because the project also uses Gemini for answer generation. Keeping embeddings and chat generation with the same provider simplifies setup.

### Q: Compare accuracy, language support, cost, speed, dimension, and deployment option.

Gemini and OpenAI embeddings are cloud APIs with strong general-purpose retrieval performance. They are easy to integrate but depend on external services and API costs.

BGE and E5 are open-source options that can run locally or privately. They are useful when privacy or offline deployment is important, but they require infrastructure.

Cohere provides embeddings and reranking models, which can be useful for production search quality. Azure OpenAI is often selected in enterprise environments because it fits Azure governance and networking.

For this project, the most important practical factor is that the embedding output dimension must match the Pinecone index dimension.

### Q: What should we know about OpenAI dimensions and optional dimension reduction?

OpenAI `text-embedding-3-small` uses 1536 dimensions by default, and `text-embedding-3-large` uses 3072 dimensions by default. Optional dimension reduction can reduce vector size, storage, and search cost.

This matters because Pinecone indexes have fixed dimensions. If the project changed embedding models, the Pinecone index might need to be recreated. The `.env` has:

```env
EMBED_DIM = 3072
```

However, the current code does not create the index using this value. It only connects to the existing Pinecone index. So the existing Pinecone index must already match the actual Gemini embedding dimension.

---

## 5. Vector Dimensionality

> **Area:** *Vector Dimensionality*
>
> **What to Research:** *384, 768, 1024, 1536, and 3072 dimensions.*
>
> **Questions You Must Answer:**
>
> - Why choose this dimensionality?
> - What is the impact on storage, search speed, memory, and retrieval quality?

### Q: Why choose this dimensionality?

Vector dimensionality must match the embedding model. The project uses Gemini embeddings and has `EMBED_DIM=3072` in `.env`.

The code connects to Pinecone using:

```python
pc.Index(INDEX_NAME)
```

Since the code does not create the index automatically, the Pinecone index `raglangchain` must already have the correct dimension.

### Q: What is the impact on storage, search speed, memory, and retrieval quality?

Higher dimensions can capture more semantic detail, which may improve retrieval. But they require more storage, memory, and compute. Lower dimensions are cheaper and faster but may reduce nuance.

For this small HR policy project, 3072 dimensions is manageable. For many documents or many tenants, vector size affects Pinecone cost and latency.

---

## 6. Metadata Structure

> **Area:** *Metadata Structure*
>
> **What to Research:** *Metadata schema for each chunk.*
>
> **Questions You Must Answer:**
>
> - What metadata should be stored?
> - Why is each needed?

### Q: What metadata should be stored?

The project should store:

```json
{
  "doc_id": "hr_policy",
  "chunk_id": "hr_policy_0001",
  "page_no": 1,
  "section": "Leave Policy",
  "source_url": "HRPolicy.pdf",
  "created_date": "2026-07-07",
  "security_group": "employees",
  "tenant_id": "default",
  "version": "v1",
  "business_domain": "HR"
}
```

This is not fully implemented yet. The current project depends mostly on loader-generated metadata.

### Q: Why is each needed?

`doc_id` identifies the document. `chunk_id` identifies the exact retrievable chunk. `page_no` supports citations. `section` improves explainability. `source_url` or `source_file` shows where the answer came from. `created_date` and `version` help avoid outdated answers. `security_group` and `tenant_id` prevent unauthorized retrieval. `business_domain` filters HR content from other domains.

---

## 7. Indexing Strategy

> **Area:** *Indexing Strategy*
>
> **What to Research:** *Vector index, keyword index, and hybrid index.*
>
> **Questions You Must Answer:**
>
> - How do we design the index for fast and accurate search?
> - How do filters work with metadata?

### Q: How do we design the index for fast and accurate search?

The project uses Pinecone as a vector index:

```python
vector_store = PineconeVectorStore(
    index=get_pinecone_index(),
    embedding=embeddings,
)
```

For fast and accurate search, the index should use the correct vector dimension, a suitable similarity metric, clean chunks, and useful metadata. The chunks should not be too noisy or too large.

The current project uses vector indexing only. Keyword and hybrid indexes are not implemented.

### Q: How do filters work with metadata?

Metadata filters restrict the search space. For example, a production system could retrieve only chunks where:

```json
{
  "tenant_id": "company_a",
  "business_domain": "HR",
  "version": "v2"
}
```

The current retriever does not use filters:

```python
retriever = vector_store.as_retriever(search_kwargs={"k": 3})
```

Filters would be added inside `search_kwargs`.

---

## 8. Semantic Search

> **Area:** *Semantic Search*
>
> **What to Research:** *Vector search, keyword search, hybrid search, and reranking.*
>
> **Questions You Must Answer:**
>
> - What types of semantic/retrieval search are available?
> - Azure AI Search hybrid search combines full-text and vector search and merges results using Reciprocal Rank Fusion.
> - Qdrant also documents hybrid retrieval using dense, sparse, and ranking stages.

### Q: What types of semantic/retrieval search are available?

The main types are vector search, keyword search, hybrid search, and reranking.

This project uses vector search. The question is embedded, compared against stored Pinecone vectors, and the top chunks are returned:

```python
docs = retriever.invoke(q)
```

Keyword search, hybrid search, and reranking are not implemented yet.

### Q: How does Azure AI Search hybrid search combine full-text and vector search using Reciprocal Rank Fusion?

Azure AI Search can run keyword search and vector search together. Keyword search finds exact words. Vector search finds meaning. Reciprocal Rank Fusion combines both ranked lists so documents that rank well in both are promoted.

This project does not use Azure AI Search, but the concept would help if the HR documents contain exact policy terms and natural-language questions.

### Q: How does Qdrant hybrid retrieval work with dense, sparse, and ranking stages?

Qdrant can combine dense vectors for semantic meaning and sparse vectors for keyword-like matching. A ranking stage merges or reranks the results.

This project uses Pinecone, not Qdrant. The idea is still relevant because HR policy search benefits from both meaning and exact term matching.

---

## 9. Hybrid Search

> **Area:** *Hybrid Search*
>
> **What to Research:** *BM25 plus vector plus metadata filter.*
>
> **Questions You Must Answer:**
>
> - Why is hybrid often better than pure vector search?
> - When does keyword search beat semantic search?

### Q: Why is hybrid often better than pure vector search?

Hybrid search is better because it combines exact word matching with semantic meaning. Pure vector search may understand "vacation" and "annual leave" as related, but it may miss exact abbreviations or policy codes.

This project currently uses pure vector search only. Hybrid search would be useful for HR terms like PF, ESI, gratuity, probation, notice period, and maternity leave.

### Q: When does keyword search beat semantic search?

Keyword search is better when exact terms matter: acronyms, dates, policy section names, employee categories, form names, and legal terms. For example, searching for "ESI" should strongly prefer chunks containing the exact acronym.

---

## 10. Reranking

> **Area:** *Reranking*
>
> **What to Research:** *Cross-encoder reranking, semantic ranker, and LLM reranking.*
>
> **Questions You Must Answer:**
>
> - Why retrieve top 20 or 50 first and rerank top 5 or 10 later?
> - How does a semantic ranker use language understanding models to rerank search results?

### Q: Why retrieve top 20 or 50 first and rerank top 5 or 10 later?

Vector search is fast and good for candidate retrieval, but it may not always rank the best answer first. Rerankers are slower but more accurate. A production system often retrieves 20 or 50 candidates, reranks them, and sends only the best 5 or 10 chunks to the LLM.

This project does not implement reranking. It retrieves only top 3 chunks:

```python
retriever = vector_store.as_retriever(search_kwargs={"k": 3})
```

### Q: How does a semantic ranker use language understanding models to rerank search results?

A semantic ranker reads the query and candidate chunk together and scores how well the chunk answers the question. For this HR project, it could rank a chunk with the exact leave rule higher than a chunk that only mentions leave generally.

---

## 11. Query Transformation

> **Area:** *Query Transformation*
>
> **What to Research:** *Query rewrite, query expansion, HyDE, multi-query, and step-back query.*
>
> **Questions You Must Answer:**
>
> - How can we improve bad user questions before retrieval?
> - LangChain describes query transformation as a way to improve retrieval when raw user queries are not optimal.

### Q: How can we improve bad user questions before retrieval?

We can rewrite unclear user questions before searching Pinecone. For example, "leave after joining?" can become "What is the employee leave eligibility policy after joining?"

This project does not implement query transformation. The raw question is sent directly to the retriever:

```python
docs = retriever.invoke(q)
```

### Q: How does LangChain query transformation help?

LangChain query transformation improves retrieval by rewriting, expanding, or decomposing questions. It helps with vague, short, misspelled, or conversational questions.

In this project, it would be especially useful for follow-up questions like "What about probation?" because the system could use chat history to create a complete standalone query.

---

## 12. Repeated User Questions

> **Area:** *Repeated User Questions*
>
> **What to Research:** *Exact cache, semantic cache, FAQ route, and prompt caching.*
>
> **Questions You Must Answer:**
>
> - What technique should be used when users ask the same or similar question repeatedly?
> - How do we avoid repeated embedding, search, and LLM cost?
> - OpenAI prompt caching is designed to reduce latency and cost when the same input prefix is reused.

### Q: What technique should be used when users ask the same or similar question repeatedly?

Use exact caching for identical questions and semantic caching for similar questions. This project does not implement caching yet. It stores chat history in PostgreSQL, but that is not the same as caching answers.

### Q: How do we avoid repeated embedding, search, and LLM cost?

Before running the RAG chain, check whether the same normalized question has already been answered for the same HR policy version. If yes, return the cached answer. For similar questions, use semantic cache lookup.

This could be added before `chain.invoke(...)` in the `/chat` route.

### Q: How does prompt caching apply here?

Prompt caching reduces cost when the same prompt prefix is reused. This project uses Gemini, not OpenAI, but application-level answer caching would still help because HR questions are often repeated.

---

## 13. Context Management

> **Area:** *Context Management*
>
> **What to Research:** *Context window, retrieved chunks, chat history, memory, and summarization.*
>
> **Questions You Must Answer:**
>
> - What should go into the LLM context?
> - What should be excluded?
> - How do we avoid sending too much context?

### Q: What should go into the LLM context?

This project sends the system instruction, chat history, retrieved HR policy chunks, and current question:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "..."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "Context:\n{context}\n\nQuestion:\n{question}")
])
```

### Q: What should be excluded?

Exclude API keys, database passwords, unrelated chunks, old irrelevant chat history, internal errors, and documents the user is not authorized to access.

`rag_langchain.py` currently prints the Google API key, which should be removed or masked before production.

### Q: How do we avoid sending too much context?

The project limits retrieval to `k=3`, which keeps context small. Better methods include reranking, metadata filtering, summarizing old history, removing duplicate text, and compressing long chunks.

---

## 14. Token Optimization

> **Area:** *Token Optimization*
>
> **What to Research:** *Context budget, chunk compression, rerank before generation, caching, and smaller models.*
>
> **Questions You Must Answer:**
>
> - How can we reduce token usage without reducing answer quality?
> - What should be done before calling the final LLM?

### Q: How can we reduce token usage without reducing answer quality?

Use better retrieval instead of sending more text. Retrieve candidates, rerank them, send only the best chunks, summarize chat history, remove repeated headers/footers, and cache repeated answers.

The current project already reduces tokens by sending only top 3 retrieved chunks.

### Q: What should be done before calling the final LLM?

Before calling Gemini, the system should validate the question, optionally rewrite it, retrieve relevant chunks, apply metadata filters, rerank if available, remove duplicate context, and build a compact prompt.

The current project retrieves and formats chunks, then calls Gemini.

---

## 15. Answer Generation

> **Area:** *Answer Generation*
>
> **What to Research:** *Prompt design, citation, grounded answers, and no-answer behavior.*
>
> **Questions You Must Answer:**
>
> - How do we force the model to answer only from retrieved context?
> - How do we show source citations?
> - What should happen when context is insufficient?

### Q: How do we force the model to answer only from retrieved context?

The system prompt says:

```text
Answer ONLY from the HR policy document.

If not found, say:
'I could not find that in the HR policy document.'
```

The model temperature is set to `0.2`, which helps make responses more factual and less creative.

### Q: How do we show source citations?

Citations are not implemented yet. The current `format_docs()` only sends chunk text:

```python
return "\n\n".join(doc.page_content for doc in docs)
```

To add citations, include metadata such as source file, page number, and section in the formatted context and return a `sources` array from the API.

### Q: What should happen when context is insufficient?

The model should not guess. It should say:

```text
I could not find that in the HR policy document.
```

This is already part of the prompt. A production version should also check low retrieval confidence before generation.

---

## 16. Evaluation

> **Area:** *Evaluation*
>
> **What to Research:** *Retrieval quality, answer quality, faithfulness, hallucination, latency, and cost.*
>
> **Questions You Must Answer:**
>
> - How do we know our RAG is better than before?
> - What metrics and test questions should we use?

### Q: How do we know our RAG is better than before?

Create a fixed set of HR policy questions with expected answers and expected source pages. Run the old and new pipelines on the same questions and compare results.

This project does not currently include automated evaluation.

### Q: What metrics and test questions should we use?

Use retrieval relevance, recall at k, answer correctness, faithfulness, hallucination rate, no-answer accuracy, latency, and cost.

Example questions:

- What is the leave policy?
- What is the probation period?
- What is the notice period?
- What benefits are mentioned?
- What is the travel reimbursement policy? If absent, the chatbot should say it cannot find the answer.

---

## 17. Guardrails

> **Area:** *Guardrails*
>
> **What to Research:** *Input validation, output validation, source grounding, PII check, unsafe prompt handling, and prompt injection.*
>
> **Questions You Must Answer:**
>
> - How do we prevent hallucination, data leakage, prompt injection, and wrong tool calls?
> - OpenAI Agents SDK includes guardrails and tracing for workflows.

### Q: How do we prevent hallucination?

Use retrieved context, a grounded prompt, low temperature, citations, no-answer behavior, and output validation. This project has the prompt and low temperature, but citations and validation are not implemented yet.

### Q: How do we prevent data leakage?

Use authentication and metadata filters such as `tenant_id` and `security_group`. Never send unauthorized chunks to the LLM. Avoid logging secrets. The current project does not implement auth or tenant filtering.

### Q: How do we prevent prompt injection?

Treat retrieved document text as data, not instructions. The system prompt should tell the model to ignore instructions inside the retrieved context that try to change behavior. This is not explicitly implemented yet.

### Q: How do we prevent wrong tool calls?

This project does not use tool-calling agents, so wrong tool calls are not currently a risk. If agents are added later, tools should be restricted and inputs validated. OpenAI Agents SDK guardrails are relevant for those future agent workflows, not for the current plain RAG implementation.

---

## 18. Observability

> **Area:** *Observability*
>
> **What to Research:** *Logs, traces, token usage, retrieval logs, and failed queries.*
>
> **Questions You Must Answer:**
>
> - What should we log for debugging?
> - Query, retrieved chunk IDs, similarity score, rerank score, final prompt token count, output token count, latency, error type.

### Q: What should we log for debugging?

Log request ID, session ID, user query, retrieved chunk IDs, source pages, similarity scores, model name, latency, no-answer cases, and error type.

Do not log API keys, database passwords, or sensitive HR information.

### Q: Should we log query, retrieved chunk IDs, similarity score, rerank score, final prompt token count, output token count, latency, and error type?

Yes. These fields help debug whether a bad response came from retrieval, prompt construction, model generation, database memory, or API failure.

The current project has minimal observability. It returns HTTP 500 errors and prints startup information, but it does not yet log retrieval scores or token usage.

---

## 19. Failure Handling

> **Area:** *Failure Handling*
>
> **What to Research:** *LLM failure, tool failure, timeout, and wrong answer.*
>
> **Questions You Must Answer:**
>
> - If one step breaks, what fallback strategies can be used?
> - Retry, fallback model, fallback keyword search, ask clarification, human handoff, no-answer response.

### Q: If one step breaks, what fallback strategies can be used?

If Gemini fails, retry or use a fallback model. If Pinecone fails, use fallback keyword search or return a temporary error. If PostgreSQL fails, answer without memory if possible and log the failure. If retrieval is weak, ask clarification or return no-answer.

The current `/chat` endpoint catches exceptions:

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### Q: When should we use retry, fallback model, keyword search, clarification, human handoff, or no-answer?

Use retry for temporary network errors. Use fallback model when Gemini is unavailable. Use keyword search when exact terms matter or vector search fails. Ask clarification when the question is vague. Use human handoff for sensitive HR cases. Use no-answer when the HR policy does not contain the answer.

---

## 20. Agent Workflow

> **Area:** *Agent Workflow*
>
> **What to Research:** *RAG agent, tool-calling agent, planner-executor, and multi-agent.*
>
> **Questions You Must Answer:**
>
> - When is plain RAG enough?
> - When do we need an agent?
> - LangGraph focuses on durable execution, streaming, and human-in-the-loop capabilities for agent orchestration.

### Q: When is plain RAG enough?

Plain RAG is enough when the user only needs answers from documents. This project is plain RAG because it answers questions from `HRPolicy.pdf`.

### Q: When do we need an agent?

An agent is needed when the system must choose tools or perform actions. Examples include applying for leave, checking leave balance, creating an HR ticket, emailing HR, or updating employee records.

The current project does not need an agent for policy Q&A.

### Q: How would LangGraph help?

LangGraph could manage multi-step HR workflows with branching, retries, streaming, and human-in-the-loop approval. It is not implemented in this project.

---

## 21. Memory And State

> **Area:** *Memory and State*
>
> **What to Research:** *Session memory, long-term memory, user preference memory, and agent memory.*
>
> **Questions You Must Answer:**
>
> - What is the difference between chat history, RAG knowledge base, and agent memory?
> - Google ADK has memory tools like preload memory and load memory.

### Q: What is the difference between chat history, RAG knowledge base, and agent memory?

Chat history is the conversation between user and assistant. In this project, it is stored in PostgreSQL using `SQLChatMessageHistory`.

The RAG knowledge base is the HR policy content stored in Pinecone as vectors.

Agent memory is persistent state used by an agent to plan and act. This project does not use agent memory.

### Q: How is memory implemented in this project?

React stores session IDs in `localStorage`. The selected session ID is sent to FastAPI. FastAPI passes it to LangChain:

```python
config={"configurable": {"session_id": req.session_id or "default_user"}}
```

LangChain uses:

```python
SQLChatMessageHistory(
    session_id=session_id,
    connection=engine,
    table_name="chat_history"
)
```

This keeps chat histories separate by session.

### Q: How do Google ADK memory tools relate?

Google ADK memory tools are useful for agent systems that need long-term memory or preloaded user state. This project does not use Google ADK. It uses LangChain SQL memory for chat history and Pinecone for document knowledge.

---

## 22. Deployment Readiness

> **Area:** *Deployment Readiness*
>
> **What to Research:** *API design, security, tenant isolation, cost control, and monitoring.*
>
> **Questions You Must Answer:**
>
> - How would we expose this as an API?
> - How do we handle authentication, tenant-specific documents, rate limits, cost limits, and logs?

### Q: How would we expose this as an API?

The project already exposes a FastAPI API:

- `POST /chat`
- `POST /new-chat`
- `GET /history`

React calls it using:

```javascript
const API_BASE = "http://localhost:8000";
```

For production, the API should run behind HTTPS and use environment-based configuration instead of hardcoded localhost URLs.

### Q: How do we handle authentication?

Authentication is not implemented. Production should use JWT, OAuth, or secure sessions. The backend should verify that the user can access the requested chat session and documents.

### Q: How do we handle tenant-specific documents?

Add `tenant_id` metadata to each Pinecone chunk and filter retrieval by the authenticated user's tenant. Also store tenant-aware chat history in PostgreSQL. This is not implemented yet.

### Q: How do we handle rate limits and cost limits?

Add per-user and per-tenant rate limits, maximum question length, request timeouts, caching, usage monitoring, and daily or monthly cost budgets. The React frontend has a 60-second Axios timeout, but backend rate limiting is not implemented.

### Q: How do we handle logs?

Use structured logs with request ID, session ID, latency, retrieved sources, model name, and error type. Do not log secrets or sensitive HR data. The current project only has basic print/error behavior.

---

## Final Summary

This project implements a plain RAG HR policy chatbot using React, FastAPI, LangChain, Gemini, Pinecone, and PostgreSQL. The implemented parts are PDF parsing, recursive chunking, Gemini embeddings, Pinecone vector retrieval, Gemini answer generation, FastAPI APIs, React chat UI, and PostgreSQL session history.

The main production improvements are custom metadata, citations, hybrid search, reranking, query transformation, caching, automated evaluation, guardrails, observability, authentication, tenant filtering, and rate/cost controls.
