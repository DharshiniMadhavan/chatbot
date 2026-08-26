import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag_langchain import build_chain, get_embeddings, get_session_history, get_vector_store

app = FastAPI()


class ChatRequest(BaseModel):
    session_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str


class ChatMessage(BaseModel):
    role: str
    content: str


class NewChatResponse(BaseModel):
    session_id: str


def get_allowed_origins():
    configured = os.getenv("CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embeddings = get_embeddings()
vector_store = get_vector_store(embeddings)
chain = build_chain(vector_store)


def get_messages(store):
    messages = getattr(store, "messages", None)
    if messages is None and hasattr(store, "get_messages"):
        messages = store.get_messages()
    if callable(messages):
        messages = messages()
    return messages or []


def message_role(message):
    class_name = message.__class__.__name__.lower()
    if "humanmessage" in class_name:
        return "user"
    if "aimessage" in class_name:
        return "assistant"
    return "system"


def serialize_message(message):
    chat_message = ChatMessage(
        role=message_role(message),
        content=getattr(message, "content", str(message)),
    )

    if hasattr(chat_message, "model_dump"):
        return chat_message.model_dump()
    return chat_message.dict()


def save_history_if_needed(session_id: str, before_count: int, question: str, answer: str):
    history_store = get_session_history(session_id)
    after_count = len(get_messages(history_store))

    if after_count == before_count:
        history_store.add_user_message(question)
        history_store.add_ai_message(answer)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        session_id = req.session_id or "default_user"
        history_store = get_session_history(session_id)
        before_count = len(get_messages(history_store))

        answer = chain.invoke(
            {"question": req.question},
            config={"configurable": {"session_id": session_id}},
        )
        answer_text = str(answer)

        save_history_if_needed(session_id, before_count, req.question, answer_text)
        return ChatResponse(answer=answer_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/new-chat", response_model=NewChatResponse)
async def new_chat():
    return NewChatResponse(session_id=f"chat_{uuid4().hex[:12]}")


@app.get("/history")
async def history(session_id: str = Query(..., min_length=1)):
    try:
        store = get_session_history(session_id)
        return {"messages": [serialize_message(message) for message in get_messages(store)]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load chat history: {e}")
