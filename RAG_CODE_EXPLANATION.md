# RAG Code Explanation

This document explains `langchain/rag_langchain.py`, `langchain/app.py`, and the frontend-to-backend data flow used by the React chat UI.

## Big Picture

The project is an HR policy chatbot implemented as a RAG pipeline.

RAG means Retrieval Augmented Generation:

1. A PDF is loaded from `langchain/HRPolicy.pdf`.
2. The PDF is split into small text chunks.
3. Each chunk is converted into an embedding vector by Google Generative AI embeddings.
4. Those vectors are stored in Pinecone.
5. When a user asks a question, the backend embeds/searches that question against Pinecone.
6. Pinecone returns the most relevant PDF chunks.
7. LangChain injects those chunks into a prompt.
8. Gemini generates an answer using only the retrieved HR policy context.
9. LangChain stores the user message and assistant answer in PostgreSQL chat history.
10. FastAPI returns the answer to React, and React displays it in the chat window.

## Runtime Components

- React frontend: `langchainfrontend/chat-ui/src/App.js`
- FastAPI backend: `langchain/app.py`
- RAG and LangChain setup: `langchain/rag_langchain.py`
- Vector database: Pinecone
- LLM and embeddings: Google Generative AI
- Chat memory: PostgreSQL table `chat_history`
- Source document: `langchain/HRPolicy.pdf`

## `langchain/rag_langchain.py` Line By Line

### Setup and Imports

Line 1 is blank.

Line 2 is a comment saying this file uses LangChain with a SQL database for chat history. The word `histroy` is just a typo in the comment.

Line 4 imports `os`, which is used to read and write environment variables.

Line 5 imports `ssl`, used later to optionally disable Google SSL certificate verification.

Line 6 imports `certifi`, which provides a trusted CA certificate bundle path.

Line 7 imports `warnings`, used to suppress LangChain deprecation warnings.

Line 8 imports `Path`, a safer object-oriented way to work with filesystem paths.

Line 9 imports `load_dotenv`, which loads environment variables from a `.env` file.

Line 10 imports `LangChainDeprecationWarning`, so only that warning category can be ignored.

Line 12 sets `BASE_DIR` to the folder containing `rag_langchain.py`. Since the file is in `langchain`, `BASE_DIR` points to `...\poc2\langchain`.

Line 13 loads environment variables from `langchain/.env`.

Line 14 hides LangChain deprecation warnings so the terminal output is cleaner.

### Proxy Cleanup

Line 16 defines `remove_dead_local_proxy_settings()`.

Lines 17 to 22 create a set of known bad proxy URLs. Port `9` is commonly used as a dead or blocked proxy placeholder.

Lines 23 to 30 loop through uppercase and lowercase proxy environment variable names.

Line 31 reads each proxy variable from the environment, removes whitespace, and removes a trailing `/`.

Lines 32 to 33 delete the environment variable if its value matches one of the dead proxy values.

Line 35 immediately calls the function so bad proxy settings are removed before API clients are created.

### SSL Certificate Configuration

Line 37 explains that certificate settings should be configured before API clients are created.

Line 38 stores the default trusted certificate bundle from `certifi`.

Line 39 uses `PINECONE_SSL_CA_CERTS` from `.env` if available. Otherwise, it falls back to the `certifi` bundle.

Line 40 sets `SSL_CERT_FILE` only if it is not already set.

Line 41 sets `REQUESTS_CA_BUNDLE` only if it is not already set. Libraries using `requests` can use this certificate bundle.

### LangChain Imports

Line 44 imports `PyPDFLoader`, which reads the PDF into LangChain `Document` objects.

Line 45 imports `RecursiveCharacterTextSplitter`, which splits long document text into smaller overlapping chunks.

Line 46 imports Google embedding and chat model wrappers.

Line 47 imports `PineconeVectorStore`, LangChain's integration with Pinecone.

Line 49 imports `ChatPromptTemplate`, used to build a structured chat prompt.

Line 49 also imports `MessagesPlaceholder`, which inserts prior chat messages into the prompt.

Line 50 imports `StrOutputParser`, which converts the LLM response into a plain string.

Line 51 imports `RunnablePassthrough`, used to pass inputs through the chain while adding new keys.

Line 52 imports `RunnableWithMessageHistory`, which wraps a chain and automatically reads/writes chat memory.

Line 55 imports `SQLChatMessageHistory`, which stores LangChain messages in SQL.

Line 56 imports `create_engine` from SQLAlchemy, used to create the PostgreSQL connection engine.

Line 59 imports the Pinecone client.

### Configuration

Lines 61 to 63 are section comments.

Line 64 sets `PDF_PATH` to `langchain/HRPolicy.pdf`.

Line 65 reads the Pinecone index name from `INDEX_NAME`; if missing, it uses `raglangchain`.

Line 66 reads the embedding model from `EMBED_MODEL`; if missing, it uses `gemini-embedding-001`.

Line 67 reads the chat model from `CHAT_MODEL`; if missing, it uses `gemini-3.5-flash`.

Line 69 defines the PostgreSQL connection string. `%40` is URL encoding for `@`, so the password is interpreted correctly.

### PostgreSQL Engine and Memory

Lines 71 to 73 are section comments.

Line 74 creates a SQLAlchemy engine connected to the `langchain_chat` PostgreSQL database.

Lines 76 to 78 are section comments.

Line 79 defines `get_session_history(session_id)`. LangChain calls this whenever it needs chat history for a specific session.

Line 80 creates a `SQLChatMessageHistory` object.

Line 81 passes the session ID. This is how separate conversations are kept separate.

Line 82 passes the already-created SQLAlchemy engine. The comment says this is the correct newer style.

Line 83 says messages should be stored in a table named `chat_history`.

Line 84 closes the constructor call.

### API Keys

Lines 86 to 88 are section comments.

Line 89 reads `GOOGLE_API_KEY` from the environment.

Line 90 reads `PINECONE_API_KEY` from the environment.

Lines 92 to 93 stop the app immediately if the Google key is missing.

Lines 95 to 96 stop the app immediately if the Pinecone key is missing.

Line 98 writes the Google key back into `os.environ`, because Google client libraries often look for this exact environment variable.

### Environment Boolean Helper

Line 100 defines `env_bool(name, default=True)`.

Line 101 reads the named environment variable.

Lines 102 to 103 return the default if the variable is not set.

Line 104 returns `False` only when the value is one of `0`, `false`, `no`, or `off`. Any other value becomes `True`.

### SSL Verification Flags

Lines 106 to 107 explain that local or corporate proxies may use self-signed certificates.

Line 108 reads `PINECONE_SSL_VERIFY`. The default is `False`, meaning Pinecone SSL verification is disabled unless explicitly enabled.

Line 109 reads `GOOGLE_SSL_VERIFY`. By default it uses the same value as `PINECONE_SSL_VERIFY`.

Line 111 defines `get_google_client_args()`.

Lines 112 to 113 return `None` when Google SSL verification is enabled, meaning normal defaults are used.

Line 114 returns an unverified SSL context when Google SSL verification is disabled.

Lines 116 to 119 disable urllib3 insecure-request warnings if Pinecone SSL verification is disabled.

### Pinecone Client

Line 121 creates a Pinecone client object.

Line 122 passes the Pinecone API key.

Line 123 passes the CA certificate bundle path.

Line 124 passes the SSL verification setting.

Line 125 closes the Pinecone constructor.

Line 127 defines `get_pinecone_index()`.

Line 128 returns a Pinecone index object for `INDEX_NAME`.

### PDF Helpers

Lines 130 to 132 are section comments.

Line 133 defines `load_pdf()`.

Line 134 creates a `PyPDFLoader` for `HRPolicy.pdf`.

Line 135 loads the PDF and returns a list of LangChain `Document` objects. Each document usually represents a page.

Line 137 defines `split_docs(pages)`.

Lines 138 to 141 create a recursive text splitter with `chunk_size=300` and `chunk_overlap=50`.

Line 139 means each chunk targets about 300 characters.

Line 140 means adjacent chunks overlap by 50 characters, which helps preserve context around chunk boundaries.

Line 142 returns the split document chunks.

### Embeddings

Lines 144 to 146 are section comments.

Line 147 defines `get_embeddings()`.

Line 148 creates a `GoogleGenerativeAIEmbeddings` object.

Line 149 ensures the model name starts with `models/`, because the Google wrapper expects names like `models/gemini-embedding-001`.

Line 150 passes SSL client arguments.

Line 151 closes the constructor.

### Vector Store

Lines 153 to 155 are section comments.

Line 156 defines `create_vector_store(chunks, embeddings)`. This is used when uploading/indexing the PDF.

Lines 157 to 160 create a LangChain Pinecone vector store using the Pinecone index and the embedding model.

Line 161 embeds and uploads the document chunks into Pinecone.

Line 162 returns the vector store object.

Line 164 defines `get_vector_store(embeddings)`. This is used at normal app startup.

Lines 165 to 168 create a vector store connected to the existing Pinecone index without uploading documents.

### Building the RAG Chain

Lines 170 to 172 are section comments.

Line 173 defines `build_chain(vector_store)`.

Line 175 converts the vector store into a retriever. `search_kwargs={"k": 3}` means each question retrieves the top 3 most relevant chunks.

Lines 177 to 181 create the Google chat model.

Line 178 selects the model from `CHAT_MODEL`.

Line 179 sets `temperature=0.2`, making responses fairly focused and less random.

Line 180 passes SSL client arguments.

Lines 183 to 203 build the chat prompt.

Line 183 starts `ChatPromptTemplate.from_messages`.

Lines 184 to 193 define the system message. This tells the model it is an HR policy assistant and must answer only from the HR policy document.

Line 194 inserts previous messages from chat history into the prompt.

Lines 195 to 202 define the human message template. It contains `{context}` for retrieved PDF chunks and `{question}` for the user question.

Line 203 closes the prompt definition.

Line 205 defines `format_docs(docs)`.

Lines 206 to 207 return a fallback string if retrieval finds no documents.

Line 208 joins each retrieved document's `page_content` with blank lines.

Line 210 defines `get_context(x)`. In the chain, `x` is the input dictionary.

Line 211 extracts and trims the question from `x`.

Lines 212 to 213 return a fallback if the question is empty.

Line 214 runs the retriever against the question. This is where Pinecone similarity search happens.

Line 215 formats the returned documents into one text block.

Lines 217 to 222 define the core RAG chain.

Line 218 uses `RunnablePassthrough.assign(context=get_context)` to keep the original input and add a new key called `context`.

Line 219 passes the enriched input into the prompt.

Line 220 sends the formatted prompt to the LLM.

Line 221 parses the LLM output into a string.

Line 224 wraps the base chain with message history.

Line 225 passes the runnable chain to wrap.

Line 226 tells LangChain how to get memory for a session.

Line 227 says the user input is stored under the key `question`.

Line 228 says prior messages should be inserted into the prompt placeholder named `history`.

Line 229 closes the wrapper constructor.

Line 231 returns the conversational RAG chain.

### One-Time PDF Upload

Lines 233 to 235 are section comments.

Line 236 defines `upload_pdf_to_pinecone_once()`. This function is for initial indexing, not for every chat request.

Line 237 prints a status message.

Line 238 loads the PDF pages.

Line 240 prints a status message.

Line 241 splits pages into chunks.

Line 243 prints a status message.

Line 244 creates the embedding model.

Line 246 prints a status message.

Line 247 uploads embedded chunks into Pinecone.

Line 249 prints completion.

Important: this function is not called automatically. You would call it manually the first time you need to populate Pinecone.

### Backend Startup Helper

Lines 251 to 253 are section comments.

Line 254 defines `is_backend_port_in_use()`, defaulting to host `127.0.0.1` and port `8000`.

Line 255 imports `socket` locally because only this function needs it.

Line 257 creates a TCP socket.

Line 258 sets a 1-second timeout.

Line 259 tries to connect to the host and port. Return code `0` means something is already listening there.

Line 261 defines `main()`.

Line 262 imports `uvicorn`, the ASGI server used to run FastAPI.

Lines 264 to 265 set the backend host and port.

Lines 266 to 269 stop startup if port 8000 is already in use.

Lines 271 to 273 print helpful startup messages.

Line 274 starts Uvicorn with `app:app`, meaning it imports the `app` object from `langchain/app.py`.

Lines 276 to 277 run `main()` only when `rag_langchain.py` is executed directly.

Lines 278 to 287 are blank lines.

## `langchain/app.py` Line By Line

Line 1 imports FastAPI application tools. `FastAPI` creates the app, `Query` validates query parameters, and `HTTPException` sends error responses.

Line 2 imports `BaseModel`, used to define request and response JSON schemas.

Line 3 imports CORS middleware so the React dev server can call the backend.

Line 4 imports `uuid4`, used to generate new chat session IDs.

Line 6 is a comment about importing common pieces from `rag_langchain.py`.

Line 7 imports four functions from `rag_langchain.py`: embeddings creation, vector store connection, chain construction, and chat history lookup.

Line 9 creates the FastAPI app instance.

Line 11 comments that CORS is being configured for React.

Lines 12 to 18 add `CORSMiddleware`.

Line 14 allows browser requests from `http://localhost:3000`, the usual React dev server.

Line 15 allows credentials such as cookies or auth headers if needed.

Line 16 allows all HTTP methods.

Line 17 allows all request headers.

Line 20 defines the request body shape for `/chat`.

Line 21 requires `session_id`.

Line 22 requires `question`.

Line 24 defines the response body shape for `/chat`.

Line 25 says the response contains an `answer` string.

Line 27 is a comment for the history endpoint model.

Line 28 defines a chat message response model.

Line 29 stores the message role: `user`, `assistant`, or `system`.

Line 30 stores the message text.

Line 33 defines the response model for `/new-chat`.

Line 34 says `/new-chat` returns a `session_id`.

Line 36 comments that the RAG chain is built once during startup.

Line 37 creates the Google embedding object.

Line 38 connects to the existing Pinecone vector store.

Line 39 builds the LangChain RAG conversation chain.

Line 41 registers a POST endpoint at `/chat`.

Line 42 defines the async route function. FastAPI parses the JSON body into `ChatRequest`.

Line 43 starts error handling.

Line 44 invokes the LangChain chain.

Line 45 passes the user question as chain input.

Line 46 passes the session ID into LangChain's configurable runtime settings. `RunnableWithMessageHistory` uses this ID to load and store PostgreSQL history.

Line 47 closes the invoke call.

Line 48 returns the answer as JSON matching `ChatResponse`.

Lines 49 to 51 catch backend errors and return HTTP 500 with the error text.

Line 54 registers a POST endpoint at `/new-chat`.

Line 55 defines the route function.

Lines 56 to 59 are a docstring explaining the endpoint.

Line 60 returns a new session ID like `chat_ab12cd34ef56`.

Line 63 registers a GET endpoint at `/history`.

Line 64 defines the route. `session_id` must be present in the query string and must have at least one character.

Lines 65 to 68 are a docstring explaining the endpoint.

Line 69 gets a SQL chat history object for this session.

Line 71 comments that different LangChain versions expose messages differently.

Line 72 tries to read `store.messages`.

Lines 73 to 74 call `store.get_messages()` if `store.messages` is unavailable.

Lines 75 to 76 call `msgs` if it is a callable object.

Line 78 creates an empty list for frontend-ready messages.

Line 79 loops through the stored LangChain messages.

Line 80 gets the message class name in lowercase.

Lines 81 to 82 map LangChain `HumanMessage` to frontend role `user`.

Lines 83 to 84 map LangChain `AIMessage` to frontend role `assistant`.

Lines 85 to 86 map anything else to role `system`.

Lines 88 to 93 create a `ChatMessage` object and append it to `result`.

Line 91 uses the message `.content` attribute if present; otherwise it stringifies the object.

Line 95 creates a list for JSON-serializable dictionaries.

Line 96 loops through the `ChatMessage` objects.

Line 97 comments that the code supports both Pydantic v1 and v2.

Lines 98 to 99 use `model_dump()` when available. That is the Pydantic v2 method.

Lines 100 to 101 use `.dict()` otherwise. That is the Pydantic v1 method.

Line 103 returns JSON shaped like `{ "messages": [...] }`.

Line 104 is blank.

## Frontend Data Flow From `App.js`

The backend files do not render the UI. The browser UI comes from `langchainfrontend/chat-ui/src/App.js`.

Important frontend lines:

- `App.js` line 7 sets `API_BASE` to `http://localhost:8000`.
- Lines 8 to 9 define localStorage keys for saved session IDs and the selected session.
- Lines 11 to 24 load session IDs from localStorage, falling back to `default_user`.
- Lines 27 to 40 create React state for sessions, selected session, messages, input text, loading flags, and errors.
- Lines 43 to 49 save sessions and selected session back to localStorage.
- Lines 55 to 70 define `loadHistory(sessionId)`, which calls `GET /history?session_id=...`.
- Lines 72 to 76 automatically load history whenever `selectedSession` changes.
- Lines 78 to 96 define `createNewChat()`, which calls `POST /new-chat`.
- Lines 98 to 134 define `sendMessage()`, which calls `POST /chat`.
- Lines 136 to 211 render the sidebar, chat messages, input box, send button, and error text.

## Complete Execution Flow

### Startup Flow

1. You start the backend, usually through `python rag_langchain.py` from the `langchain` folder or by running Uvicorn directly.
2. `rag_langchain.py` loads `.env`, configures SSL/proxy settings, reads API keys, creates the Pinecone client, and defines helper functions.
3. `main()` starts Uvicorn with `uvicorn.run("app:app", ...)`.
4. Uvicorn imports `langchain/app.py`.
5. `app.py` imports functions from `rag_langchain.py`.
6. `app.py` creates the FastAPI app and configures CORS.
7. `app.py` runs:
   - `embeddings = get_embeddings()`
   - `vector_store = get_vector_store(embeddings)`
   - `chain = build_chain(vector_store)`
8. The backend is now ready to receive requests at `http://localhost:8000`.

### First-Time Indexing Flow

This happens only if you manually call `upload_pdf_to_pinecone_once()`.

1. `load_pdf()` reads `HRPolicy.pdf`.
2. `split_docs()` splits the PDF text into chunks.
3. `get_embeddings()` creates the Google embedding model.
4. `create_vector_store()` connects to Pinecone.
5. `vector_store.add_documents(chunks)` embeds each chunk and uploads vectors to Pinecone.
6. After this, normal chat requests can retrieve relevant chunks from Pinecone.

### Page Load Flow

1. React starts in the browser.
2. `App.js` reads known chat sessions from localStorage.
3. It selects the previous selected session or falls back to `default_user`.
4. The `useEffect` watching `selectedSession` calls `loadHistory(selectedSession)`.
5. React sends `GET http://localhost:8000/history?session_id=...`.
6. FastAPI runs `history()` in `app.py`.
7. `history()` calls `get_session_history(session_id)`.
8. PostgreSQL returns stored LangChain messages.
9. FastAPI maps LangChain message classes to frontend roles.
10. FastAPI returns `{ "messages": [...] }`.
11. React stores the returned messages in `messages` state.
12. The chat window renders those messages.

### New Chat Flow

1. The user clicks `+ New Chat`.
2. React runs `createNewChat()`.
3. React sends `POST http://localhost:8000/new-chat`.
4. FastAPI generates a new ID with `uuid4`.
5. FastAPI returns `{ "session_id": "chat_xxxxxxxxxxxx" }`.
6. React adds the new ID to `sessions`.
7. React sets the selected session to the new ID.
8. The selected-session effect loads history for the new session.
9. Since the session is new, no history is returned yet.

### Asking a Question Flow

1. The user types a question and clicks Send.
2. React runs `sendMessage(e)`.
3. React prevents the form's default page refresh.
4. React trims the question.
5. React immediately adds the user message to the UI for a fast response feel.
6. React sends:

```json
{
  "session_id": "default_user",
  "question": "What is the leave policy?"
}
```

to `POST http://localhost:8000/chat`.

7. FastAPI validates the JSON body using `ChatRequest`.
8. FastAPI calls:

```python
chain.invoke(
    {"question": req.question},
    config={"configurable": {"session_id": req.session_id or "default_user"}},
)
```

9. `RunnableWithMessageHistory` uses the `session_id` to load previous messages from PostgreSQL.
10. `RunnablePassthrough.assign(context=get_context)` calls `get_context`.
11. `get_context` retrieves the top 3 relevant chunks from Pinecone.
12. `format_docs` joins those chunks into one context string.
13. The prompt is built with:
    - system instruction
    - previous chat history
    - retrieved document context
    - current user question
14. The prompt is sent to Gemini through `ChatGoogleGenerativeAI`.
15. Gemini returns an answer.
16. `StrOutputParser` converts the model response into a plain string.
17. `RunnableWithMessageHistory` saves the new human message and AI message to PostgreSQL.
18. FastAPI wraps the string in `ChatResponse`.
19. FastAPI returns:

```json
{
  "answer": "..."
}
```

20. React appends the assistant answer to `messages`.
21. The UI re-renders and shows the bot reply.

## Important Data Shapes

### `/chat` Request

```json
{
  "session_id": "chat_abc123",
  "question": "What is the work from home policy?"
}
```

### `/chat` Response

```json
{
  "answer": "The answer generated from the HR policy context."
}
```

### `/new-chat` Response

```json
{
  "session_id": "chat_ab12cd34ef56"
}
```

### `/history` Response

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is the leave policy?"
    },
    {
      "role": "assistant",
      "content": "..."
    }
  ]
}
```

## How Memory Works

Memory is controlled by the `session_id`.

If two users or two browser sessions use different session IDs, their chat histories are stored separately. If they use the same session ID, they share the same chat history.

React stores only the list of session IDs and the selected session in localStorage. The actual conversation messages are stored in PostgreSQL through `SQLChatMessageHistory`.

## How Retrieval Works

When the user asks a question:

1. The question is passed to the retriever.
2. The retriever uses the embedding model to compare the question with indexed PDF chunks in Pinecone.
3. Pinecone returns the top 3 most similar chunks.
4. Those chunks are inserted into `{context}` in the prompt.
5. The LLM answers using that context.

The key line is `retriever = vector_store.as_retriever(search_kwargs={"k": 3})` in `rag_langchain.py`. The value `k=3` controls how many document chunks are retrieved per question.

## Notes and Risks

- The PostgreSQL password is hard-coded in `rag_langchain.py`. In a real project, this should move into `.env`.
- SSL verification defaults to disabled for Pinecone. That may help local development, but production should enable verification.
- `upload_pdf_to_pinecone_once()` is not called automatically. If Pinecone has no indexed PDF chunks, the chatbot will not have useful context.
- The frontend only allows `http://localhost:8000` as the backend URL.
- The backend CORS config only allows frontend origin `http://localhost:3000`.
