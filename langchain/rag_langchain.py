import os
import ssl
import warnings
from pathlib import Path

import certifi
from dotenv import load_dotenv
from pinecone import Pinecone
from sqlalchemy import create_engine

from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

PDF_PATH = str(BASE_DIR / "HRPolicy.pdf")
INDEX_NAME = os.getenv("INDEX_NAME", "raglangchain").strip()
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001").strip()
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.5-flash").strip()
POSTGRES_CONNECTION = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:Gain%4012345@localhost:5432/langchain_chat",
)
if POSTGRES_CONNECTION.startswith("postgres://"):
    POSTGRES_CONNECTION = POSTGRES_CONNECTION.replace("postgres://", "postgresql://", 1)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY missing")

if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY missing")

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY


def remove_dead_local_proxy_settings():
    dead_proxy_values = {
        "http://127.0.0.1:9",
        "https://127.0.0.1:9",
        "http://localhost:9",
        "https://localhost:9",
    }
    proxy_names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )

    for name in proxy_names:
        value = os.environ.get(name, "").strip().rstrip("/")
        if value in dead_proxy_values:
            os.environ.pop(name, None)


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


remove_dead_local_proxy_settings()

PINECONE_SSL_CA_CERTS = os.getenv("PINECONE_SSL_CA_CERTS") or certifi.where()
PINECONE_SSL_VERIFY = env_bool("PINECONE_SSL_VERIFY", False)
GOOGLE_SSL_VERIFY = env_bool("GOOGLE_SSL_VERIFY", PINECONE_SSL_VERIFY)

os.environ.setdefault("SSL_CERT_FILE", PINECONE_SSL_CA_CERTS)
os.environ.setdefault("REQUESTS_CA_BUNDLE", PINECONE_SSL_CA_CERTS)

if not PINECONE_SSL_VERIFY:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

engine = create_engine(POSTGRES_CONNECTION)
pinecone_client = Pinecone(
    api_key=PINECONE_API_KEY,
    ssl_ca_certs=PINECONE_SSL_CA_CERTS,
    ssl_verify=PINECONE_SSL_VERIFY,
)


def get_google_client_args():
    if GOOGLE_SSL_VERIFY:
        return None
    return {"verify": ssl._create_unverified_context()}


def get_session_history(session_id: str):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection=engine,
        table_name="chat_history",
    )


def get_pinecone_index():
    return pinecone_client.Index(INDEX_NAME)


def load_pdf():
    return PyPDFLoader(PDF_PATH).load()


def split_docs(pages):
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    return splitter.split_documents(pages)


def get_embeddings():
    model = EMBED_MODEL if EMBED_MODEL.startswith("models/") else f"models/{EMBED_MODEL}"
    return GoogleGenerativeAIEmbeddings(
        model=model,
        client_args=get_google_client_args(),
    )


def create_vector_store(chunks, embeddings):
    vector_store = get_vector_store(embeddings)
    vector_store.add_documents(chunks)
    return vector_store


def get_vector_store(embeddings):
    return PineconeVectorStore(
        index=get_pinecone_index(),
        embedding=embeddings,
    )


def format_docs(docs):
    if not docs:
        return "No relevant context found."
    return "\n\n".join(doc.page_content for doc in docs)


def build_prompt():
    return ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an HR policy assistant.

Answer ONLY from the HR policy document.

If not found, say:
'I could not find that in the HR policy document.'
""",
        ),
        MessagesPlaceholder(variable_name="history"),
        (
            "human",
            """Context:
{context}

Question:
{question}""",
        ),
    ])


def build_chain(vector_store):
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    llm = ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        temperature=0.2,
        client_args=get_google_client_args(),
    )

    def get_context(inputs):
        question = inputs.get("question", "").strip()
        if not question:
            return "No valid question provided."
        return format_docs(retriever.invoke(question))

    base_chain = (
        RunnablePassthrough.assign(context=get_context)
        | build_prompt()
        | llm
        | StrOutputParser()
    )

    return RunnableWithMessageHistory(
        runnable=base_chain,
        get_session_history=get_session_history,
        input_messages_key="question",
        history_messages_key="history",
    )


def upload_pdf_to_pinecone_once():
    print("Loading PDF...")
    pages = load_pdf()

    print("Splitting...")
    chunks = split_docs(pages)

    print("Embedding...")
    embeddings = get_embeddings()

    print("Uploading to Pinecone...")
    create_vector_store(chunks, embeddings)

    print("Upload completed.")


def is_backend_port_in_use(host: str = "127.0.0.1", port: int = 8002) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def main():
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))

    if is_backend_port_in_use(host, port):
        print(f"Backend is already running at http://{host}:{port}")
        print("Use the existing server, or stop it before starting another one.")
        return

    print("Starting backend API for the React frontend...")
    print(f"Backend URL: http://localhost:{port}")
    print("Frontend should call POST /chat, POST /new-chat, and GET /history")
    uvicorn.run("app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
