import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { api } from "../api";
import { Button } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";

type Message = { id: string; role: "user" | "assistant"; content: string; provider: string; model: string; created_at: string };
type Chat = { id: string; title: string; project_id: string | null; created_at: string; updated_at: string };
type Project = { id: string; name: string; created_at: string };

export default function AIPage() {
  const { notify } = useApp();
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState("");
  const [panelOpen, setPanelOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [movingChat, setMovingChat] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [showNewProject, setShowNewProject] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const chats = useResource(() => api.get<{ items: Chat[] }>("/ai/chats?limit=60"), []);
  const projects = useResource(() => api.get<{ items: Project[] }>("/ai/projects"), []);

  useEffect(() => {
    if (!activeChatId) return;
    api.get<{ items: Message[] }>(`/ai/chats/${activeChatId}/messages`)
      .then((r) => setMessages(r.items));
  }, [activeChatId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function startChat() {
    setBusy("new-chat");
    try {
      const chat = await api.post<Chat>("/ai/chats", { title: "New chat" });
      setActiveChatId(chat.id);
      setMessages([]);
      setPanelOpen(false);
      await chats.reload();
    } finally {
      setBusy("");
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    if (!input.trim() || !activeChatId) return;
    const content = input.trim();
    setInput("");
    const tempId = `temp-${Date.now()}`;
    setMessages((prev) => [...prev, { id: tempId, role: "user", content, provider: "", model: "", created_at: new Date().toISOString() }]);
    setBusy("sending");
    try {
      const reply = await api.post<Message>(`/ai/chats/${activeChatId}/messages`, { content });
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId),
        { id: tempId + "-u", role: "user", content, provider: "", model: "", created_at: new Date().toISOString() },
        reply
      ]);
      await chats.reload();
    } catch (error) {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      setInput(content);
      notify(error instanceof Error ? error.message : "Send failed", "error");
    } finally {
      setBusy("");
    }
  }

  function handleKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); }
  }

  async function deleteChat(chatId: string) {
    try {
      await api.delete(`/ai/chats/${chatId}`);
      if (activeChatId === chatId) { setActiveChatId(null); setMessages([]); }
      setDeleteConfirm(null);
      await chats.reload();
      notify("Chat deleted", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Delete failed", "error");
    }
  }

  async function moveChat(chatId: string, projectId: string | null) {
    try {
      await api.post(`/ai/chats/${chatId}/move`, { project_id: projectId });
      setMovingChat(null);
      await chats.reload();
      notify("Chat moved", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Move failed", "error");
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();
    if (!newProjectName.trim()) return;
    try {
      await api.post("/ai/projects", { name: newProjectName.trim() });
      setNewProjectName("");
      setShowNewProject(false);
      await projects.reload();
      notify("Project created", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not create project", "error");
    }
  }

  function openChat(chat: Chat) {
    setActiveChatId(chat.id);
    setMessages([]);
    setPanelOpen(false);
    setMovingChat(null);
  }

  const ungrouped = (chats.data?.items ?? []).filter((c) => !c.project_id);
  const grouped = (projects.data?.items ?? []).map((p) => ({
    project: p,
    chats: (chats.data?.items ?? []).filter((c) => c.project_id === p.id),
  }));
  const totalChats = (chats.data?.items ?? []).length;

  return (
    <div className="ai-shell">

      {/* ── Main chat area ───────────────────────────────────────────────── */}
      <div className="ai-main">
        {/* Topbar: title + toggle */}
        <div className="ai-topbar">
          <div className="ai-topbar-left">
            <h1 className="ai-page-title">AI</h1>
            {activeChatId && (
              <span className="ai-active-title">
                {(chats.data?.items ?? []).find((c) => c.id === activeChatId)?.title ?? "Chat"}
              </span>
            )}
          </div>
          <div className="ai-topbar-right">
            <button type="button" className="ai-new-btn" onClick={startChat} disabled={busy === "new-chat"}>
              ＋ New chat
            </button>
            <button
              type="button"
              className={panelOpen ? "ai-panel-toggle ai-panel-toggle-active" : "ai-panel-toggle"}
              onClick={() => setPanelOpen((v) => !v)}
              title={panelOpen ? "Close history" : "Open history & projects"}
              aria-expanded={panelOpen}
            >
              <span className="ai-panel-toggle-icon">⊞</span>
              <span>History {totalChats > 0 ? `· ${totalChats}` : ""}</span>
            </button>
          </div>
        </div>

        {/* Chat */}
        {activeChatId ? (
          <>
            <div className="ai-messages">
              {messages.length === 0 && (
                <div className="ai-empty-chat">
                  <p>Start the conversation — try "Help me write a follow-up for a carbon credit prospect" or "Analyse my pipeline."</p>
                </div>
              )}
              {messages.map((msg) => (
                <div key={msg.id} className={msg.role === "user" ? "ai-bubble ai-bubble-user" : "ai-bubble ai-bubble-assistant"}>
                  <p className="ai-bubble-role">{msg.role === "user" ? "You" : `AI${msg.model ? ` · ${msg.model}` : ""}`}</p>
                  <div className="ai-bubble-content">{msg.content}</div>
                </div>
              ))}
              {busy === "sending" && (
                <div className="ai-bubble ai-bubble-assistant">
                  <p className="ai-bubble-role">AI</p>
                  <div className="ai-bubble-content ai-typing"><span /><span /><span /></div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            <form className="ai-input-row" onSubmit={sendMessage}>
              <textarea
                className="ai-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask anything… Enter to send · Shift+Enter for new line"
                rows={2}
                disabled={busy === "sending"}
              />
              <Button type="submit" busy={busy === "sending"} disabled={!input.trim()}>Send</Button>
            </form>
          </>
        ) : (
          <div className="ai-welcome">
            <div className="ai-welcome-inner">
              <p className="ai-welcome-icon">🤖</p>
              <h2>off_CRM AI</h2>
              <p>Ask anything about your leads, campaigns, or email strategy. Uses whichever provider you have connected in AI Connectors.</p>
              <Button onClick={startChat} busy={busy === "new-chat"}>Start a new chat</Button>
              {totalChats > 0 && (
                <button type="button" className="ai-open-history" onClick={() => setPanelOpen(true)}>
                  Or open history to continue a previous chat →
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Right panel: history + projects (slides in/out) ──────────────── */}
      {panelOpen && (
        <div className="ai-panel-overlay" onClick={() => setPanelOpen(false)} aria-hidden="true" />
      )}
      <aside className={panelOpen ? "ai-panel ai-panel-open" : "ai-panel"} aria-label="Chat history and projects">
        <div className="ai-panel-head">
          <strong>History &amp; Projects</strong>
          <button type="button" className="ai-panel-close" onClick={() => setPanelOpen(false)} aria-label="Close panel">✕</button>
        </div>

        <div className="ai-panel-scroll">
          {/* Ungrouped / recent */}
          {ungrouped.length > 0 && (
            <div className="ai-panel-section">
              <p className="ai-panel-label">Recent</p>
              {ungrouped.map((chat) => (
                <div key={chat.id} className={activeChatId === chat.id ? "ai-chat-item ai-chat-active" : "ai-chat-item"}>
                  <button type="button" className="ai-chat-title" onClick={() => openChat(chat)}>{chat.title}</button>
                  <div className="ai-chat-actions">
                    <button type="button" className="ai-icon-btn" title="Move to project" onClick={() => setMovingChat(movingChat === chat.id ? null : chat.id)}>📁</button>
                    <button type="button" className="ai-icon-btn ai-delete-btn" title="Delete chat" onClick={() => setDeleteConfirm(chat.id)}>🗑</button>
                  </div>
                  {movingChat === chat.id && (
                    <div className="ai-move-dropdown">
                      <p className="ai-move-label">Move to project</p>
                      {(projects.data?.items ?? []).map((p) => (
                        <button key={p.id} type="button" className="ai-move-option" onClick={() => moveChat(chat.id, p.id)}>{p.name}</button>
                      ))}
                      {!(projects.data?.items?.length) && <p className="ai-move-empty">No projects yet — create one below.</p>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Projects */}
          {grouped.map(({ project, chats: pChats }) => (
            <div key={project.id} className="ai-panel-section">
              <p className="ai-panel-label">📁 {project.name}</p>
              {pChats.length ? pChats.map((chat) => (
                <div key={chat.id} className={activeChatId === chat.id ? "ai-chat-item ai-chat-active" : "ai-chat-item"}>
                  <button type="button" className="ai-chat-title" onClick={() => openChat(chat)}>{chat.title}</button>
                  <div className="ai-chat-actions">
                    <button type="button" className="ai-icon-btn" title="Move" onClick={() => setMovingChat(movingChat === chat.id ? null : chat.id)}>📁</button>
                    <button type="button" className="ai-icon-btn ai-delete-btn" title="Delete" onClick={() => setDeleteConfirm(chat.id)}>🗑</button>
                  </div>
                  {movingChat === chat.id && (
                    <div className="ai-move-dropdown">
                      <p className="ai-move-label">Move to</p>
                      {(projects.data?.items ?? []).filter((p) => p.id !== project.id).map((p) => (
                        <button key={p.id} type="button" className="ai-move-option" onClick={() => moveChat(chat.id, p.id)}>{p.name}</button>
                      ))}
                      <button type="button" className="ai-move-option ai-move-remove" onClick={() => moveChat(chat.id, null)}>Remove from project</button>
                    </div>
                  )}
                </div>
              )) : <p className="ai-panel-empty">No chats in this project yet.</p>}
            </div>
          ))}

          {!ungrouped.length && !grouped.length && (
            <p className="ai-panel-empty" style={{ padding: "20px 14px" }}>No chats yet. Start one with the button above.</p>
          )}

          {/* New project */}
          <div className="ai-panel-section">
            {showNewProject ? (
              <form className="ai-new-project-form" onSubmit={createProject}>
                <input className="ai-new-project-input" value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} placeholder="Project name" autoFocus />
                <button type="submit" className="ai-new-project-btn">Create</button>
                <button type="button" className="ai-new-project-cancel" onClick={() => setShowNewProject(false)}>✕</button>
              </form>
            ) : (
              <button type="button" className="ai-new-project-toggle" onClick={() => setShowNewProject(true)}>+ New project</button>
            )}
          </div>
        </div>
      </aside>

      {/* ── Delete confirmation ─────────────────────────────────────────── */}
      {deleteConfirm && (
        <div className="ai-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="ai-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <p className="ai-confirm-title">Delete this chat?</p>
            <p className="ai-confirm-body">This permanently deletes the conversation and all its messages. It cannot be undone.</p>
            <div className="button-row">
              <Button tone="danger" onClick={() => deleteChat(deleteConfirm)}>Yes, delete</Button>
              <Button tone="ghost" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
