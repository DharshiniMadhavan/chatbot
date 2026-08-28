

import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./App.css";
// api base url
const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";
const STORAGE_SESSIONS_KEY = "chatbot_session_ids";
const STORAGE_SELECTED_KEY = "chatbot_selected_session";

function loadStoredSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_SESSIONS_KEY);
    if (!raw) return ["default_user"];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) {
      const clean = parsed.filter((x) => typeof x === "string" && x.trim());
      return clean.length ? clean : ["default_user"];
    }
    return ["default_user"];
  } catch {
    return ["default_user"];
  }
}

export default function App() {
  const [sessions, setSessions] = useState(() => loadStoredSessions());

  const [selectedSession, setSelectedSession] = useState(() => {
    const stored = localStorage.getItem(STORAGE_SELECTED_KEY);
    const initialSessions = loadStoredSessions();
    if (stored && initialSessions.includes(stored)) return stored;
    return initialSessions[0];
  });

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  // Persist sessions + selected session (NO overwrite-before-load issue)
  useEffect(() => {
    localStorage.setItem(STORAGE_SESSIONS_KEY, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    if (selectedSession) localStorage.setItem(STORAGE_SELECTED_KEY, selectedSession);
  }, [selectedSession]);

  const sortedSessions = useMemo(() => {
    return [...sessions].sort((a, b) => b.localeCompare(a));
  }, [sessions]);

  const loadHistory = async (sessionId) => {
    setErrorText("");
    setHistoryLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/history`, {
        params: { session_id: sessionId },
      });
      setMessages(Array.isArray(res.data?.messages) ? res.data.messages : []);
    } catch (err) {
      console.error(err);
      setMessages([]);
      const detail = err?.response?.data?.detail;
      if (detail) {
        setErrorText(String(detail));
      } else if (err?.code === "ERR_NETWORK") {
        setErrorText(`Could not reach backend at ${API_BASE}. Start FastAPI and check CORS.`);
      } else {
        setErrorText("Could not load history.");
      }
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedSession) return;
    loadHistory(selectedSession);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSession]);

  const createNewChat = async () => {
    setErrorText("");
    setHistoryLoading(true);
    setMessages([]);
    setQuestion("");

    try {
      const res = await axios.post(`${API_BASE}/new-chat`);
      const newId = String(res.data?.session_id || "").trim();
      if (!newId) throw new Error("Invalid session id from backend.");

      setSessions((prev) => (prev.includes(newId) ? prev : [...prev, newId]));
      setSelectedSession(newId);
    } catch (err) {
      console.error(err);
      setErrorText("Could not create new chat session.");
      setHistoryLoading(false);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || loading || historyLoading) return;
    if (!selectedSession) return;

    setErrorText("");
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await axios.post(
        `${API_BASE}/chat`,
        { session_id: selectedSession, question: q },
        { timeout: 60000 }
      );

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: String(res.data?.answer ?? "") },
      ]);
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: detail ? String(detail) : "Error contacting server.",
        },
      ]);
      setErrorText(detail ? String(detail) : "Message failed. Ensure backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="layout">
        {/* LEFT SIDEBAR */}
        <aside className="sidebar">
          <div className="sidebar-header">Chats</div>

          <div className="new-session-row">
            <button onClick={createNewChat} style={{ width: "100%" }} disabled={loading || historyLoading}>
              + New Chat
            </button>
          </div>

          <div className="session-list">
            {sortedSessions.map((id) => (
              <div
                key={id}
                className={`session-item ${selectedSession === id ? "active" : ""}`}
              >
                <button className="session-select" onClick={() => setSelectedSession(id)}>
                  {id}
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* RIGHT CHAT */}
        <main className="chat">
          <div className="chat-header">
            <div className="chat-title">HR Policy Chatbot</div>
            <div className="chat-subtitle">Current Chat: {selectedSession}</div>
          </div>

          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="empty-state">No chat history for this session yet.</div>
            ) : (
              messages.map((m, idx) => (
                <div
                  key={`${m.role}-${idx}`}
                  className={`msg ${m.role === "user" ? "user" : "assistant"}`}
                >
                  <div className="msg-role">{m.role === "user" ? "You" : "Bot"}</div>
                  <div className="msg-content">{m.content}</div>
                </div>
              ))
            )}

            {(loading || historyLoading) && (
              <div className="msg assistant">
                <div className="msg-role">Bot</div>
                <div className="msg-content">Thinking...</div>
              </div>
            )}
          </div>

          <form className="chat-input-row" onSubmit={sendMessage}>
            <input
              type="text"
              placeholder="Ask about HR policy..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={loading || historyLoading}
            />
            <button type="submit" disabled={loading || historyLoading}>
              Send
            </button>
          </form>

          {errorText && <div className="error-text">{errorText}</div>}
        </main>
      </div>
    </div>
  );

  
}
