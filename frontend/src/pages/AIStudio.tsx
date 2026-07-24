import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent
} from "react";
import { api } from "../api";
import { Badge, Button, Field, Modal, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type {
  AIBootstrap,
  AIContextState,
  AIConversation,
  AIEgressCall,
  AIIntake,
  AIMessage,
  AIModel,
  AIProject,
  Paginated
} from "../types";
import { Loadable } from "./shared";

const CONVERSATION_KEY = "off-crm-ai-conversation";
const MODEL_KEY = "off-crm-ai-model";
const DRAWER_KEY = "off-crm-ai-drawer-open";

function storedValue(key: string, fallback = ""): string {
  if (typeof window === "undefined") return fallback;
  return window.localStorage.getItem(key) ?? fallback;
}

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function formatWhen(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function modelLabel(model: AIModel): string {
  return `${model.name} · ${model.model || model.provider_type}`;
}

function trustTone(tier: string): string {
  if (tier === "A") return "success";
  if (tier === "B") return "blue";
  if (tier === "C") return "warning";
  return "danger";
}

function modelStatus(model: AIModel): string {
  if (model.ai_eligible) return `Tier ${model.effective_trust_tier || model.trust_tier} · eligible`;
  return `Tier ${model.effective_trust_tier || model.trust_tier} · blocked for chat`;
}

export default function AIStudio() {
  const { notify, selectCampaign, refreshCampaigns } = useApp();
  const [activeConversationId, setActiveConversationId] = useState(
    storedValue(CONVERSATION_KEY)
  );
  const [selectedModelId, setSelectedModelId] = useState(
    storedValue(MODEL_KEY)
  );
  const [drawerOpen, setDrawerOpen] = useState(
    storedValue(DRAWER_KEY, "true") !== "false"
  );
  const [drawerTab, setDrawerTab] = useState<"chats" | "projects">("chats");
  const [search, setSearch] = useState("");
  const [prompt, setPrompt] = useState("");
  const [allowFailover, setAllowFailover] = useState(true);
  const [busy, setBusy] = useState("");
  const [version, setVersion] = useState(0);
  const [projectOpen, setProjectOpen] = useState(false);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [intake, setIntake] = useState<AIIntake | null>(null);
  const [intakeMode, setIntakeMode] = useState<"" | "generate" | "parse_send">("");
  const [contextOpen, setContextOpen] = useState(false);
  const [egress, setEgress] = useState<AIEgressCall | null>(null);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const bootstrap = useResource<AIBootstrap>(() => api.get("/ai/bootstrap"), [version]);
  const messages = useResource<Paginated<AIMessage>>(
    () =>
      activeConversationId
        ? api.get(`/ai/conversations/${activeConversationId}/messages?limit=500`)
        : Promise.resolve({ items: [], total: 0 }),
    [activeConversationId, version]
  );
  const context = useResource<AIContextState>(
    () =>
      activeConversationId
        ? api.get(`/ai/conversations/${activeConversationId}/context`)
        : Promise.resolve({
            id: "",
            scope_type: "conversation",
            scope_id: "",
            current_task: "",
            rolling_summary: "",
            done: [],
            pending: [],
            entity_facts: {},
            decisions: [],
            constraints: [],
            updated_at: ""
          }),
    [activeConversationId, version]
  );

  const projects = bootstrap.data?.projects ?? [];
  const conversations = bootstrap.data?.conversations ?? [];
  const models = bootstrap.data?.models ?? [];
  const eligibleModels = models.filter((model) => model.ai_eligible);
  const outreachModels = models.filter(
    (model) => model.task_eligibility?.outreach_draft
  );
  const activeConversation =
    conversations.find((item) => item.id === activeConversationId) ?? null;
  const selectedModel =
    models.find((item) => item.id === selectedModelId) ?? null;

  useEffect(() => {
    if (!bootstrap.data) return;
    if (
      activeConversationId &&
      !bootstrap.data.conversations.some((item) => item.id === activeConversationId)
    ) {
      setActiveConversationId("");
      localStorage.removeItem(CONVERSATION_KEY);
    }
    if (
      selectedModelId &&
      !bootstrap.data.models.some(
        (item) => item.id === selectedModelId && item.ai_eligible
      )
    ) {
      setSelectedModelId("");
      localStorage.removeItem(MODEL_KEY);
    }
  }, [bootstrap.data, activeConversationId, selectedModelId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.data?.total, busy]);

  useEffect(() => {
    localStorage.setItem(DRAWER_KEY, String(drawerOpen));
  }, [drawerOpen]);

  useEffect(
    () => () => {
      recognitionRef.current?.stop();
    },
    []
  );

  const filteredConversations = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return conversations;
    return conversations.filter((item) =>
      [item.title, item.project_name, item.last_message]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [conversations, search]);

  const filteredProjects = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter((item) =>
      [item.name, item.description].join(" ").toLowerCase().includes(needle)
    );
  }, [projects, search]);

  function chooseConversation(id: string) {
    setActiveConversationId(id);
    localStorage.setItem(CONVERSATION_KEY, id);
    const conversation = conversations.find((item) => item.id === id);
    if (conversation?.selected_profile_id) {
      setSelectedModelId(conversation.selected_profile_id);
      localStorage.setItem(MODEL_KEY, conversation.selected_profile_id);
    }
    if (window.innerWidth <= 900) setDrawerOpen(false);
  }

  function chooseModel(id: string) {
    setSelectedModelId(id);
    if (id) localStorage.setItem(MODEL_KEY, id);
    else localStorage.removeItem(MODEL_KEY);
  }

  async function newConversation(projectId = ""): Promise<AIConversation> {
    const conversation = await api.post<AIConversation>("/ai/conversations", {
      title: "New chat",
      project_id: projectId,
      selected_profile_id: selectedModelId,
      task_type: "public_general"
    });
    chooseConversation(conversation.id);
    setVersion((current) => current + 1);
    window.setTimeout(() => composerRef.current?.focus(), 0);
    return conversation;
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const text = prompt.trim();
    if (!text || busy) return;
    setBusy("send");
    try {
      let conversationId = activeConversationId;
      if (!conversationId) {
        const created = await newConversation();
        conversationId = created.id;
      }
      setPrompt("");
      await api.post(`/ai/conversations/${conversationId}/messages`, {
        prompt: text,
        selected_profile_id: selectedModelId,
        task_type: "public_general",
        allow_failover: allowFailover
      });
      setVersion((current) => current + 1);
    } catch (error) {
      setPrompt(text);
      notify(error instanceof Error ? error.message : "The AI request was blocked", "error");
    } finally {
      setBusy("");
    }
  }

  function composerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  async function retry(message: AIMessage) {
    if (!activeConversationId) return;
    setBusy(`retry-${message.id}`);
    try {
      await api.post(`/ai/conversations/${activeConversationId}/retry`, {
        assistant_message_id: message.id,
        selected_profile_id: selectedModelId
      });
      setVersion((current) => current + 1);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Retry failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function inspectEgress(callId: string) {
    if (!callId) return;
    setBusy(`egress-${callId}`);
    try {
      setEgress(await api.get<AIEgressCall>(`/ai/egress/${callId}`));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Audit record unavailable", "error");
    } finally {
      setBusy("");
    }
  }

  async function updateConversation(
    conversation: AIConversation,
    changes: Partial<Pick<AIConversation, "title" | "project_id" | "pinned" | "archived">>
  ) {
    try {
      await api.patch(`/ai/conversations/${conversation.id}`, changes);
      if (changes.archived && conversation.id === activeConversationId) {
        setActiveConversationId("");
        localStorage.removeItem(CONVERSATION_KEY);
      }
      setVersion((current) => current + 1);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Chat could not be updated", "error");
    }
  }

  async function renameConversation(conversation: AIConversation) {
    const title = window.prompt("Chat title", conversation.title)?.trim();
    if (title && title !== conversation.title) {
      await updateConversation(conversation, { title });
    }
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("project");
    try {
      const project = await api.post<AIProject>("/ai/projects", {
        name: data.get("name"),
        description: data.get("description"),
        instructions: data.get("instructions")
      });
      setProjectOpen(false);
      form.reset();
      setVersion((current) => current + 1);
      await newConversation(project.id);
      notify("Project and first chat created", "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Project could not be created", "error");
    } finally {
      setBusy("");
    }
  }

  async function inspectIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (activeConversationId) data.set("conversation_id", activeConversationId);
    data.set("selected_mode", intakeMode);
    setBusy("inspect-intake");
    try {
      const result = await api.upload<AIIntake>("/ai/intakes/inspect", data);
      setIntake(result);
      setIntakeMode(result.selected_mode || result.detected_mode || intakeMode);
      if (result.status === "failed") {
        notify(result.error || "The file could not be parsed", "error");
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : "File inspection failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function chooseIntakeMode(mode: "generate" | "parse_send") {
    if (!intake) return;
    setBusy("intake-mode");
    try {
      const updated = await api.post<AIIntake>(`/ai/intakes/${intake.id}/mode`, {
        mode
      });
      setIntake(updated);
      setIntakeMode(mode);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Mode could not be selected", "error");
    } finally {
      setBusy("");
    }
  }

  async function commitIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!intake) return;
    if (intakeMode === "generate" && !outreachModels.length) {
      notify(
        "Generate mode needs an eligible Tier A provider. Add one under Connectors, or choose Parse & send.",
        "error"
      );
      return;
    }
    const data = new FormData(event.currentTarget);
    setBusy("commit-intake");
    try {
      const result = await api.post<{
        campaign_id: string;
        contacts_added: number;
        drafts_created: number;
        missing_email_count: number;
        excluded: number;
      }>(`/ai/intakes/${intake.id}/commit`, {
        campaign_name: data.get("campaign_name"),
        daily_send_limit: Number(data.get("daily_send_limit") || 20),
        selected_mode: intakeMode,
        selected_profile_id:
          intakeMode === "generate" &&
          selectedModel?.task_eligibility?.outreach_draft
            ? selectedModelId
            : ""
      });
      selectCampaign(result.campaign_id);
      refreshCampaigns();
      notify(
        `${result.contacts_added} contacts and ${result.drafts_created} review drafts created`,
        "success"
      );
      setIntakeOpen(false);
      setIntake(null);
      window.location.hash = "drafts";
    } catch (error) {
      notify(error instanceof Error ? error.message : "Campaign creation failed", "error");
    } finally {
      setBusy("");
    }
  }

  function toggleDictation() {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const speechWindow = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionLike;
      webkitSpeechRecognition?: new () => SpeechRecognitionLike;
    };
    const Recognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      notify("Voice dictation is not supported by this browser", "info");
      return;
    }
    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = navigator.language || "en-IN";
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      if (transcript) {
        setPrompt((current) => `${current}${current ? " " : ""}${transcript}`);
      }
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => {
      setListening(false);
      notify("Voice dictation stopped before it captured text", "info");
    };
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  const selectedProject = projects.find(
    (project) => project.id === activeConversation?.project_id
  );

  return (
    <div className={`ai-studio ${drawerOpen ? "ai-drawer-open" : ""}`}>
      <section className="ai-workspace" aria-label="OFF_AI workspace">
        <header className="ai-header">
          <div>
            <p className="eyebrow">OFF_AI</p>
            <h1>{activeConversation?.title || "How can I help?"}</h1>
            <p>
              {selectedProject
                ? `${selectedProject.name} · public and owner-approved context only`
                : "Private CRM data stays local. Models receive only an inspected task packet."}
            </p>
          </div>
          <div className="ai-header-actions">
            {activeConversationId ? (
              <Button tone="ghost" onClick={() => setContextOpen(true)}>
                Context
              </Button>
            ) : null}
            <Button tone="secondary" onClick={() => void newConversation()}>
              + New chat
            </Button>
            {!drawerOpen ? (
              <button
                className="ai-drawer-toggle"
                onClick={() => setDrawerOpen(true)}
                aria-label="Open chat and project history"
              >
                History
              </button>
            ) : null}
          </div>
        </header>

        <div className="ai-privacy-strip">
          <span>✓ No mailbox access</span>
          <span>✓ No CRM database access</span>
          <span>✓ Email addresses stay local</span>
          <span>✓ Exact egress audit</span>
        </div>

        <div className="ai-model-bar">
          <label>
            <span>Model</span>
            <select
              value={selectedModelId}
              onChange={(event) => chooseModel(event.target.value)}
              aria-label="AI model"
            >
              <option value="">Automatic eligible routing</option>
              {models.map((model) => (
                <option key={model.id} value={model.id} disabled={!model.ai_eligible}>
                  {modelLabel(model)} · Tier {model.effective_trust_tier || model.trust_tier}
                  {!model.ai_eligible ? " (blocked)" : ""}
                </option>
              ))}
            </select>
          </label>
          {selectedModel ? (
            <div className="ai-model-meta">
              <Badge tone={trustTone(selectedModel.effective_trust_tier || selectedModel.trust_tier)}>
                {modelStatus(selectedModel)}
              </Badge>
              <span>{selectedModel.jurisdiction}</span>
              <span>{selectedModel.retention_policy.replaceAll("_", " ")}</span>
              <span>
                {selectedModel.usage?.today.requests || 0}
                {selectedModel.rpd_limit ? `/${selectedModel.rpd_limit}` : ""} today
              </span>
            </div>
          ) : (
            <div className="ai-model-meta">
              <span>
                {eligibleModels.length
                  ? `${eligibleModels.length} eligible model${eligibleModels.length === 1 ? "" : "s"}`
                  : "No eligible AI provider"}
              </span>
              {!eligibleModels.length ? <a href="#connections">Open Connectors</a> : null}
            </div>
          )}
          <label className="ai-failover">
            <input
              type="checkbox"
              checked={allowFailover}
              onChange={(event) => setAllowFailover(event.target.checked)}
            />
            Same-tier failover
          </label>
        </div>

        <div className="ai-thread" aria-live="polite">
          {bootstrap.loading || bootstrap.error ? (
            <Loadable loading={bootstrap.loading} error={bootstrap.error} />
          ) : !activeConversationId || !messages.data?.items.length ? (
            <div className="ai-empty">
              <div className="ai-orb">AI</div>
              <h2>Work with public, approved context</h2>
              <p>
                Ask a research question, start a project, or import a campaign file.
                OFF_CRM constructs the provider packet locally and records exactly what left.
              </p>
              <div className="ai-starters">
                <button onClick={() => setPrompt("Create a public research plan for identifying 100 CBAM advisers in Europe.")}>
                  Build a public research plan
                </button>
                <button onClick={() => setPrompt("Compare these public positioning options and identify the clearest one.")}>
                  Review public positioning
                </button>
                <button onClick={() => setIntakeOpen(true)}>
                  Import a campaign file
                </button>
              </div>
            </div>
          ) : messages.loading || messages.error ? (
            <Loadable loading={messages.loading} error={messages.error} />
          ) : (
            <div className="ai-messages">
              {messages.data.items.map((message) => (
                <article className={`ai-message ai-message-${message.role}`} key={message.id}>
                  <div className="ai-message-avatar">{message.role === "assistant" ? "AI" : "You"}</div>
                  <div className="ai-message-body">
                    <header>
                      <strong>{message.role === "assistant" ? "OFF_AI" : "You"}</strong>
                      <time>{formatWhen(message.created_at)}</time>
                      {message.status !== "complete" ? (
                        <Badge tone={message.status === "blocked" ? "danger" : "warning"}>
                          {message.status}
                        </Badge>
                      ) : null}
                    </header>
                    <div className="ai-message-content">{message.content}</div>
                    {message.role === "assistant" ? (
                      <footer>
                        <span>
                          {message.model || "model"} · Tier {message.trust_tier || "unknown"}
                        </span>
                        {message.egress_call_id ? (
                          <button
                            onClick={() => void inspectEgress(message.egress_call_id)}
                            disabled={busy === `egress-${message.egress_call_id}`}
                          >
                            Inspect packet
                          </button>
                        ) : null}
                        <button
                          onClick={() => void retry(message)}
                          disabled={busy === `retry-${message.id}`}
                        >
                          Retry
                        </button>
                      </footer>
                    ) : null}
                  </div>
                </article>
              ))}
              {busy === "send" ? (
                <article className="ai-message ai-message-assistant ai-thinking">
                  <div className="ai-message-avatar">AI</div>
                  <div className="ai-message-body"><span /><span /><span /></div>
                </article>
              ) : null}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form className="ai-composer" onSubmit={send}>
          <textarea
            ref={composerRef}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={composerKeyDown}
            placeholder={
              eligibleModels.length
                ? "Message OFF_AI with public, non-sensitive information…"
                : "Connect an eligible model first…"
            }
            rows={2}
            maxLength={30000}
            disabled={!eligibleModels.length || busy === "send"}
            aria-label="Prompt"
          />
          <div className="ai-composer-actions">
            <div>
              <button
                type="button"
                onClick={() => setIntakeOpen(true)}
                title="Inspect and import a campaign file"
                aria-label="Attach campaign file"
              >
                +
              </button>
              <button
                type="button"
                className={listening ? "is-listening" : ""}
                onClick={toggleDictation}
                title="Voice dictation"
                aria-label={listening ? "Stop voice dictation" : "Start voice dictation"}
              >
                ◉
              </button>
            </div>
            <span>{prompt.length.toLocaleString()}/30,000</span>
            <button
              className="ai-send"
              type="submit"
              disabled={!prompt.trim() || !eligibleModels.length || busy === "send"}
              aria-label="Send prompt"
            >
              {busy === "send" ? "…" : "↑"}
            </button>
          </div>
          <p>
            Enter sends · Shift+Enter adds a line · Requests for Gmail, CRM records,
            credentials, private context, or email addresses are blocked before egress.
          </p>
        </form>
      </section>

      {drawerOpen ? (
        <aside className="ai-history-drawer" aria-label="Chat and project history">
          <header>
            <div>
              <strong>History</strong>
              <small>{conversations.length} chats · {projects.length} projects</small>
            </div>
            <button onClick={() => setDrawerOpen(false)} aria-label="Close chat and project history">
              ×
            </button>
          </header>
          <div className="ai-drawer-tabs" role="tablist">
            <button
              className={drawerTab === "chats" ? "active" : ""}
              onClick={() => setDrawerTab("chats")}
              role="tab"
              aria-selected={drawerTab === "chats"}
            >
              Chats
            </button>
            <button
              className={drawerTab === "projects" ? "active" : ""}
              onClick={() => setDrawerTab("projects")}
              role="tab"
              aria-selected={drawerTab === "projects"}
            >
              Projects
            </button>
          </div>
          <label className="ai-history-search">
            <span>⌕</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={`Search ${drawerTab}`}
              aria-label={`Search ${drawerTab}`}
            />
          </label>
          {drawerTab === "chats" ? (
            <>
              <button className="ai-new-item" onClick={() => void newConversation()}>
                <span>+</span> New chat
              </button>
              <div className="ai-history-list">
                {filteredConversations.map((conversation) => (
                  <article
                    className={conversation.id === activeConversationId ? "active" : ""}
                    key={conversation.id}
                  >
                    <button className="ai-history-main" onClick={() => chooseConversation(conversation.id)}>
                      <span>{conversation.pinned ? "◆" : "◇"}</span>
                      <span>
                        <strong>{conversation.title}</strong>
                        <small>
                          {conversation.project_name || "Standalone"} · {formatWhen(conversation.updated_at)}
                        </small>
                        {conversation.last_message ? <em>{conversation.last_message}</em> : null}
                      </span>
                    </button>
                    <div className="ai-history-actions">
                      <button
                        onClick={() =>
                          void updateConversation(conversation, {
                            pinned: !conversation.pinned
                          })
                        }
                        title={conversation.pinned ? "Unpin" : "Pin"}
                      >
                        {conversation.pinned ? "Unpin" : "Pin"}
                      </button>
                      <button onClick={() => void renameConversation(conversation)}>Rename</button>
                      <button
                        onClick={() =>
                          void updateConversation(conversation, { archived: true })
                        }
                      >
                        Archive
                      </button>
                    </div>
                  </article>
                ))}
                {!filteredConversations.length ? (
                  <p className="ai-history-empty">No matching chats.</p>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <button className="ai-new-item" onClick={() => setProjectOpen(true)}>
                <span>+</span> New project
              </button>
              <div className="ai-project-list">
                {filteredProjects.map((project) => (
                  <article key={project.id}>
                    <button onClick={() => void newConversation(project.id)}>
                      <span className="ai-project-icon">P</span>
                      <span>
                        <strong>{project.name}</strong>
                        <small>{project.conversation_count} chats</small>
                        {project.description ? <em>{project.description}</em> : null}
                      </span>
                    </button>
                    <div>
                      <button
                        onClick={() =>
                          void api.download(
                            `/ai/projects/${project.id}/export?format=md`,
                            `${project.name}.md`
                          )
                        }
                      >
                        Markdown
                      </button>
                      <button
                        onClick={() =>
                          void api.download(
                            `/ai/projects/${project.id}/export?format=html`,
                            `${project.name}.html`
                          )
                        }
                      >
                        HTML
                      </button>
                    </div>
                  </article>
                ))}
                {!filteredProjects.length ? (
                  <p className="ai-history-empty">No matching projects.</p>
                ) : null}
              </div>
            </>
          )}
          <footer>
            <a href="#connections">Manage models and Gmail</a>
            <span>History stays in OFF_CRM</span>
          </footer>
        </aside>
      ) : null}

      <Modal
        open={projectOpen}
        onClose={() => setProjectOpen(false)}
        title="Create AI project"
        description="Projects group chats and reusable public instructions. They never grant a model access to CRM data."
      >
        <form className="form-stack" onSubmit={createProject}>
          <Field label="Project name">
            <input name="name" required maxLength={160} autoFocus />
          </Field>
          <Field label="Description">
            <textarea name="description" rows={3} maxLength={5000} />
          </Field>
          <Field
            label="Approved public instructions"
            hint="Do not place email addresses, CRM records, credentials, or mailbox content here."
          >
            <textarea name="instructions" rows={7} maxLength={30000} />
          </Field>
          <div className="modal-actions">
            <Button type="button" tone="ghost" onClick={() => setProjectOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" busy={busy === "project"}>Create project</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={intakeOpen}
        onClose={() => {
          setIntakeOpen(false);
          setIntake(null);
        }}
        title="Campaign file intake"
        description="Inspect first. Email addresses are masked from public previews and reattached locally only after generation."
        wide
      >
        {!intake ? (
          <form className="form-stack" onSubmit={inspectIntake}>
            <Field label="Campaign file" hint="CSV, XLSX, XLS, PDF, TXT, or Markdown">
              <input name="file" type="file" accept=".csv,.xlsx,.xls,.pdf,.txt,.md" required />
            </Field>
            <div className="form-grid">
              <Field label="Mode">
                <select
                  value={intakeMode}
                  onChange={(event) =>
                    setIntakeMode(event.target.value as "" | "generate" | "parse_send")
                  }
                >
                  <option value="">Detect automatically</option>
                  <option value="generate">Generate from a template</option>
                  <option value="parse_send">Parse pre-written messages</option>
                </select>
              </Field>
              <Field label="Approved public positioning">
                <input
                  name="public_positioning"
                  defaultValue={bootstrap.data?.defaults.public_positioning || ""}
                  placeholder="What the sender publicly does"
                />
              </Field>
            </div>
            <Field
              label="Template"
              hint="Required for Generate mode. Names and email addresses are not placed in the provider packet."
            >
              <textarea
                name="template_text"
                rows={8}
                placeholder="Subject and body mould for personalisation…"
              />
            </Field>
            <div className="form-note">
              <strong>Human approval remains mandatory</strong>
              <span>
                Imported or generated drafts cannot enter the send queue until reviewed and approved.
                The campaign daily limit cannot exceed 20.
              </span>
            </div>
            <div className="modal-actions">
              <Button type="button" tone="ghost" onClick={() => setIntakeOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" busy={busy === "inspect-intake"}>Inspect file</Button>
            </div>
          </form>
        ) : (
          <div className="form-stack">
            <div className={`ai-intake-status ai-intake-${intake.status}`}>
              <strong>{intake.status.replaceAll("_", " ")}</strong>
              <span>
                {intake.public_preview.row_count || 0} rows · detected{" "}
                {intake.detected_mode ? intake.detected_mode.replaceAll("_", " ") : "unknown"}
              </span>
              {intake.error ? <p>{intake.error}</p> : null}
            </div>
            {intake.status === "needs_choice" ? (
              <div className="ai-mode-choice">
                <button
                  onClick={() => void chooseIntakeMode("generate")}
                  disabled={busy === "intake-mode"}
                >
                  <strong>Generate</strong>
                  <span>Use the supplied template and approved public facts.</span>
                </button>
                <button
                  onClick={() => void chooseIntakeMode("parse_send")}
                  disabled={busy === "intake-mode"}
                >
                  <strong>Parse & send</strong>
                  <span>Preserve pre-written subject and message columns.</span>
                </button>
              </div>
            ) : null}
            {intake.public_preview.rows?.length ? (
              <div className="table-wrap ai-intake-preview">
                <table>
                  <thead>
                    <tr>
                      {Object.keys(intake.public_preview.rows[0]).map((column) => (
                        <th key={column}>{column.replaceAll("_", " ")}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {intake.public_preview.rows.slice(0, 8).map((row, index) => (
                      <tr key={index}>
                        {Object.keys(intake.public_preview.rows?.[0] || {}).map((column) => (
                          <td key={column}>{String(row[column] || "")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {intake.status === "ready" ? (
              <form className="form-stack" onSubmit={commitIntake}>
                <div className="form-grid">
                  <Field label="Campaign name">
                    <input name="campaign_name" required maxLength={160} />
                  </Field>
                  <Field label="Daily send limit" hint="Hard maximum: 20">
                    <input name="daily_send_limit" type="number" min={1} max={20} defaultValue={20} />
                  </Field>
                </div>
                <div className="danger-note">
                  <strong>Review gate</strong>
                  Every resulting draft remains pending. Missing email addresses are placed in the
                  Apollo enrichment queue; duplicates are excluded before credits or sending.
                </div>
                {intakeMode === "generate" ? (
                  outreachModels.length ? (
                    <div className="form-note">
                      <strong>
                        {selectedModel?.task_eligibility?.outreach_draft
                          ? `Using ${selectedModel.name}`
                          : "Automatic Tier A routing"}
                      </strong>
                      <span>
                        Only providers approved for person-level outreach can receive one public
                        POI profile at a time.
                      </span>
                    </div>
                  ) : (
                    <div className="danger-note">
                      <strong>No eligible outreach model</strong>
                      Add and verify a Tier A provider under Connectors, or start over and choose
                      Parse &amp; send.
                    </div>
                  )
                ) : null}
                <div className="modal-actions">
                  <Button
                    type="button"
                    tone="ghost"
                    onClick={() => {
                      setIntake(null);
                      setIntakeMode("");
                    }}
                  >
                    Start over
                  </Button>
                  <Button
                    type="submit"
                    busy={busy === "commit-intake"}
                    disabled={intakeMode === "generate" && !outreachModels.length}
                  >
                    Create review campaign
                  </Button>
                </div>
              </form>
            ) : null}
          </div>
        )}
      </Modal>

      <Modal
        open={contextOpen}
        onClose={() => setContextOpen(false)}
        title="Local context state"
        description="This compact state is maintained by OFF_CRM. Providers cannot search or open it."
        wide
      >
        {context.loading || context.error ? (
          <Loadable loading={context.loading} error={context.error} />
        ) : context.data ? (
          <div className="ai-context-grid">
            <section>
              <h3>Current task</h3>
              <p>{context.data.current_task || "No current task"}</p>
            </section>
            <section>
              <h3>Rolling summary</h3>
              <p>{context.data.rolling_summary || "No summary yet"}</p>
            </section>
            <section>
              <h3>Done</h3>
              {context.data.done.length ? (
                <ul>{context.data.done.map((item) => <li key={item}>{item}</li>)}</ul>
              ) : <p>Nothing recorded yet.</p>}
            </section>
            <section>
              <h3>Pending</h3>
              {context.data.pending.length ? (
                <ul>{context.data.pending.map((item) => <li key={item}>{item}</li>)}</ul>
              ) : <p>Nothing pending.</p>}
            </section>
            <section className="ai-context-wide">
              <h3>Entity facts</h3>
              <pre>{JSON.stringify(context.data.entity_facts, null, 2)}</pre>
            </section>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(egress)}
        onClose={() => setEgress(null)}
        title="Provider egress inspector"
        description="The exact constructed packet and routing decision recorded before the provider call."
        wide
      >
        {egress ? (
          <div className="ai-egress">
            <div className="review-meta">
              <div><span>Provider</span><strong>{egress.provider_name}</strong></div>
              <div><span>Model</span><strong>{egress.model || "default"}</strong></div>
              <div><span>Trust</span><strong>Tier {egress.trust_tier}</strong></div>
              <div><span>Status</span><strong>{egress.status}</strong></div>
            </div>
            <div className="ai-egress-facts">
              <span>{egress.jurisdiction}</span>
              <span>{egress.retention_policy.replaceAll("_", " ")}</span>
              <span>{egress.input_tokens} input tokens</span>
              <span>{egress.duration_ms} ms</span>
            </div>
            {egress.blocked_reasons.length ? (
              <div className="danger-note">
                <strong>Blocked before egress</strong>
                {egress.blocked_reasons.map((reason) => <p key={reason}>{reason}</p>)}
              </div>
            ) : null}
            <Field label="Exact packet">
              <textarea readOnly rows={16} value={JSON.stringify(egress.payload, null, 2)} />
            </Field>
            {egress.response_text ? (
              <Field label="Provider response">
                <textarea readOnly rows={10} value={egress.response_text} />
              </Field>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
