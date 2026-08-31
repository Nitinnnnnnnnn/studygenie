import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  Plus,
  Send,
  Trash2,
  BookOpen,
  Layers,
  FileText,
  Sparkles,
  AlertCircle,
  X,
  ChevronRight,
  CheckCircle2,
} from "lucide-react";
import api from "../api/client";

const ChatInterface = ({ preselectedDocId }) => {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState("");
  const [documents, setDocuments] = useState([]);
  const [selectedDocFilter, setSelectedDocFilter] = useState(
    preselectedDocId || "all",
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState(null);

  const messagesEndRef = useRef(null);
  const formatMessageTime = (dateString) => {
    if (!dateString) return "";

    const utcDate = new Date(
      dateString.endsWith("Z") || dateString.includes("+")
        ? dateString
        : `${dateString}Z`,
    );

    return utcDate.toLocaleTimeString("en-IN", {
      timeZone: "Asia/Kolkata",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Fetch all documents for filter dropdown
  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await api.get("/documents/");
        setDocuments(res.data);
      } catch (err) {
        console.error("Failed to load documents", err);
      }
    };
    fetchDocs();
  }, []);

  // Update selected doc if prop changes
  useEffect(() => {
    if (preselectedDocId) {
      setSelectedDocFilter(preselectedDocId);
    }
  }, [preselectedDocId]);

  // Fetch chat sessions list
  const fetchSessions = async () => {
    try {
      setIsLoading(true);
      const res = await api.get("/chat/sessions");
      setSessions(res.data);
      if (res.data.length > 0 && !activeSessionId) {
        setActiveSessionId(res.data[0].id);
      }
    } catch (err) {
      console.error("Failed to load sessions", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  // Fetch messages when active session changes
  useEffect(() => {
    if (!activeSessionId) return;

    const fetchSessionMessages = async () => {
      try {
        const res = await api.get(`/chat/sessions/${activeSessionId}`);
        setMessages(res.data.messages || []);
      } catch (err) {
        console.error("Failed to load session messages", err);
      }
    };

    fetchSessionMessages();
  }, [activeSessionId]);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const handleCreateNewSession = async () => {
    try {
      const res = await api.post("/chat/sessions", {
        title: "New Study Session",
      });
      setSessions([res.data, ...sessions]);
      setActiveSessionId(res.data.id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to create session", err);
    }
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await api.delete(`/chat/sessions/${sessionId}`);
      const updated = sessions.filter((s) => s.id !== sessionId);
      setSessions(updated);
      if (activeSessionId === sessionId) {
        setActiveSessionId(updated.length > 0 ? updated[0].id : null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!inputQuery.trim() || isSending) return;

    let currentSessionId = activeSessionId;

    // If no active session, create one first
    if (!currentSessionId) {
      try {
        const newSession = await api.post("/chat/sessions", {
          title: inputQuery.slice(0, 30),
        });
        setSessions([newSession.data, ...sessions]);
        currentSessionId = newSession.data.id;
        setActiveSessionId(currentSessionId);
      } catch (err) {
        alert("Failed to initialize chat session.");
        return;
      }
    }

    const userText = inputQuery.trim();
    setInputQuery("");

    // Optimistic UI for user message
    const tempUserMsg = {
      id: Date.now(),
      sender: "user",
      content: userText,
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsSending(true);

    try {
      const docIds =
        selectedDocFilter === "all" ? null : [parseInt(selectedDocFilter, 10)];
      const res = await api.post(`/chat/sessions/${currentSessionId}/ask`, {
        question: userText,
        document_ids: docIds,
      });

      setMessages((prev) => [...prev, res.data]);
      fetchSessions(); // Refresh session title in sidebar
    } catch (err) {
      const errorMsg = {
        id: Date.now() + 1,
        sender: "assistant",
        content: `⚠️ Error: ${err.response?.data?.detail || "Failed to generate response. Check backend connection."}`,
        sources: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const handleQuickQuestion = (q) => {
    setInputQuery(q);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 h-[calc(100vh-5rem)] flex gap-6">
      {/* Left Sidebar: Sessions List */}
      <div className="w-80 hidden lg:flex flex-col bg-slate-900/80 border border-slate-800 rounded-2xl p-4 backdrop-blur-sm">
        <button
          onClick={handleCreateNewSession}
          className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20 transition-all mb-4"
        >
          <Plus className="w-4 h-4" />
          New Study Session
        </button>

        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2 mb-2">
          Chat History ({sessions.length})
        </div>

        <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => setActiveSessionId(s.id)}
              className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer text-sm transition-all ${
                activeSessionId === s.id
                  ? "bg-indigo-600/15 border border-indigo-500/30 text-white font-medium"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <MessageSquare
                  className={`w-4 h-4 flex-shrink-0 ${activeSessionId === s.id ? "text-indigo-400" : "text-slate-500"}`}
                />
                <span className="truncate text-xs">{s.title}</span>
              </div>
              <button
                onClick={(e) => handleDeleteSession(e, s.id)}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 transition-opacity"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {sessions.length === 0 && !isLoading && (
            <div className="text-center py-8 text-xs text-slate-500">
              No sessions yet. Ask a question to start!
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Panel */}
      <div className="flex-1 flex flex-col bg-slate-900/80 border border-slate-800 rounded-2xl backdrop-blur-sm overflow-hidden">
        {/* Top Control Bar */}
        <div className="p-4 border-b border-slate-800/80 bg-slate-900/50 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">RAG Course Tutor</h3>
              <p className="text-[11px] text-slate-400">
                Strictly grounded in uploaded notes with exact page citations
              </p>
            </div>
          </div>

          {/* Document Scope Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Scope:</span>
            <select
              value={selectedDocFilter}
              onChange={(e) => setSelectedDocFilter(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="all">🔍 Search Across All Notes</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  📄 {d.filename}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto py-12">
              <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4 border border-indigo-500/20 shadow-lg shadow-indigo-500/10">
                <Sparkles className="w-8 h-8" />
              </div>
              <h4 className="text-lg font-bold text-white">
                Ask Anything from Your Study Notes
              </h4>
              <p className="text-sm text-slate-400 mt-2">
                StudyGenie searches your notes in ChromaDB, matches relevant
                passages using Mistral embeddings, and provides a clear, cited
                explanation.
              </p>

              {/* Starter Question Chips */}
              <div className="mt-6 flex flex-col w-full gap-2 text-left">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider text-center mb-1">
                  Suggested Inquiries
                </p>
                <button
                  onClick={() =>
                    handleQuickQuestion(
                      "Summarize the core concepts and definitions from my notes.",
                    )
                  }
                  className="p-3 text-xs bg-slate-800/80 hover:bg-indigo-600/15 hover:border-indigo-500/30 text-slate-300 border border-slate-700 rounded-xl transition-all"
                >
                  💡 "Summarize the core concepts and definitions from my
                  notes."
                </button>
                <button
                  onClick={() =>
                    handleQuickQuestion(
                      "What are the key formulas, algorithms, or methodologies mentioned?",
                    )
                  }
                  className="p-3 text-xs bg-slate-800/80 hover:bg-indigo-600/15 hover:border-indigo-500/30 text-slate-300 border border-slate-700 rounded-xl transition-all"
                >
                  📐 "What are the key formulas or methodologies mentioned?"
                </button>
                <button
                  onClick={() =>
                    handleQuickQuestion(
                      "What are the most likely exam questions based on this material?",
                    )
                  }
                  className="p-3 text-xs bg-slate-800/80 hover:bg-indigo-600/15 hover:border-indigo-500/30 text-slate-300 border border-slate-700 rounded-xl transition-all"
                >
                  🎯 "What are the most likely exam questions based on this
                  material?"
                </button>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-2xl rounded-2xl p-4 sm:p-5 text-sm leading-relaxed ${
                  msg.sender === "user"
                    ? "bg-gradient-to-tr from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                    : "bg-slate-800/90 border border-slate-700/80 text-slate-200 shadow-sm"
                }`}
              >
                {/* Message Content */}
                <div className="whitespace-pre-wrap font-normal">
                  {msg.content}
                </div>

                {/* Sources & Citations Badges */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-700/60">
                    <p className="text-[11px] font-semibold text-indigo-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5" />
                      Retrieved Vector Sources ({msg.sources.length}):
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.sources.map((src, sIdx) => (
                        <button
                          key={sIdx}
                          onClick={() => setSelectedCitation(src)}
                          className="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-medium flex items-center gap-1.5 transition-all"
                        >
                          <FileText className="w-3 h-3 text-indigo-400" />
                          <span>{src.filename}</span>
                          <span className="text-slate-400">P.{src.page}</span>
                          {src.score && (
                            <span className="text-[10px] bg-indigo-500/20 px-1 py-0.2 rounded text-indigo-200">
                              {Math.round(src.score * 100)}% match
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-500 mt-1 px-1">
                {formatMessageTime(msg.created_at)}
              </span>
            </div>
          ))}

          {isSending && (
            <div className="flex items-start">
              <div className="bg-slate-800 border border-slate-700 rounded-2xl p-4 text-slate-300 text-xs flex items-center gap-3">
                <div className="w-4 h-4 border-2 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin" />
                <span>
                  Searching ChromaDB & synthesizing answer via Mistral AI...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <form
          onSubmit={handleSendMessage}
          className="p-4 border-t border-slate-800 bg-slate-900/60 flex items-center gap-3"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Ask a question from your study material..."
            disabled={isSending}
            className="flex-1 bg-slate-800/80 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || isSending}
            className="p-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-lg shadow-indigo-500/20 disabled:opacity-40 transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* Citation Inspector Modal / Drawer */}
      {selectedCitation && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 relative">
            <button
              onClick={() => setSelectedCitation(null)}
              className="absolute top-4 right-4 p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white">
                  {selectedCitation.filename}
                </h4>
                <p className="text-xs text-indigo-400 font-semibold">
                  Page {selectedCitation.page} • Similarity Score:{" "}
                  {Math.round((selectedCitation.score || 0.85) * 100)}%
                </p>
              </div>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs font-mono text-slate-300 leading-relaxed max-h-72 overflow-y-auto">
              {selectedCitation.chunk_text}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 text-right">
              <button
                onClick={() => setSelectedCitation(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-xl"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
