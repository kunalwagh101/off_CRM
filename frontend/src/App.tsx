import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, AUTH_REQUIRED_EVENT, getToken, setToken } from "./api";
import { Button, Field, Modal } from "./components";
import { AppContext } from "./context";
import { useResource } from "./hooks";
import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import Contacts from "./pages/Contacts";
import Discovery from "./pages/Discovery";
import Drafts from "./pages/Drafts";
import Queue from "./pages/Queue";
import Deliverability from "./pages/Deliverability";
import SalesTracker from "./pages/SalesTracker";
import Experiments from "./pages/Experiments";
import ImageReview from "./pages/ImageReview";
import VideoEditor from "./pages/VideoEditor";
import Posting from "./pages/Posting";
import AI from "./pages/AI";
import Connectors from "./pages/Connectors";
import Egress from "./pages/Egress";
import Memory from "./pages/Memory";
import Recall from "./pages/Recall";
import Settings from "./pages/Settings";
import type { AuthSession, Campaign, Paginated } from "./types";

const CAMPAIGN_KEY = "offsetx-active-campaign";
const pages = {
  dashboard: Dashboard,
  campaigns: Campaigns,
  discovery: Discovery,
  contacts: Contacts,
  drafts: Drafts,
  queue: Queue,
  deliverability: Deliverability,
  sales: SalesTracker,
  experiments: Experiments,
  imagereview: ImageReview,
  videoeditor: VideoEditor,
  posting: Posting,
  connectors: Connectors,
  egress: Egress,
  memory: Memory,
  recall: Recall,
  ai: AI,
  settings: Settings
};
type Page = keyof typeof pages;

const navigation: Array<{ page: Page; label: string; icon: string; group?: string }> = [
  { page: "ai", label: "AI", icon: "✦", group: "AI" },
  { page: "connectors", label: "Connectors", icon: "⚡" },
  { page: "egress", label: "What was sent", icon: "◉" },
  { page: "memory", label: "Memory", icon: "◈" },
  { page: "recall", label: "Past emails", icon: "⟲" },
  { page: "dashboard", label: "Overview", icon: "⌂", group: "Workspace" },
  { page: "campaigns", label: "Campaigns", icon: "◫" },
  { page: "discovery", label: "Lead discovery", icon: "⌕" },
  { page: "contacts", label: "Contacts", icon: "◎" },
  { page: "drafts", label: "Draft review", icon: "✎", group: "Outreach" },
  { page: "queue", label: "Send queue", icon: "➤" },
  { page: "deliverability", label: "Deliverability", icon: "✓" },
  { page: "sales", label: "Sales tracker", icon: "↗", group: "Sales" },
  { page: "experiments", label: "Experiments", icon: "A/B" },
  { page: "imagereview", label: "Image review", icon: "▣", group: "Images" },
  { page: "videoeditor", label: "Video editor", icon: "▶", group: "Video" },
  { page: "posting", label: "Posting", icon: "◷", group: "Distribution" },
  { page: "settings", label: "Settings", icon: "⚙", group: "System" }
];

function currentPage(): Page {
  const value = window.location.hash.replace(/^#\/?/, "") as Page;
  return value in pages ? value : "dashboard";
}

export function LoginScreen({ onLogin }: { onLogin: (session: AuthSession) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await api.post<{ authenticated: boolean; username: string }>("/auth/login", {
        username: String(data.get("username") ?? ""),
        password: String(data.get("password") ?? "")
      });
      onLogin({ configured: true, authenticated: result.authenticated, username: result.username, expires_at: null });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand"><span className="brand-symbol">off_</span><span><strong>off_CRM</strong><small>Your outreach, your data</small></span></div>
        <p className="eyebrow">Protected demo</p>
        <h1 id="login-title">Sign in to the CRM</h1>
        <p className="login-copy">Use the temporary demo credentials configured privately in Render.</p>
        <form className="form-stack" onSubmit={submit}>
          <Field label="Username"><input name="username" autoComplete="username" required autoFocus /></Field>
          <Field label="Password"><input name="password" type="password" autoComplete="current-password" required /></Field>
          {error ? <p className="login-error" role="alert">{error}</p> : null}
          <Button type="submit" busy={busy}>Sign in</Button>
        </form>
        <p className="login-safety">Demo mode uses the local outbox. Gmail is not required.</p>
      </section>
    </main>
  );
}

function AuthenticatedApp({ auth, onLogout }: { auth: AuthSession; onLogout: () => void }) {
  const [page, setPage] = useState<Page>(currentPage());
  const [campaignId, setCampaignId] = useState(localStorage.getItem(CAMPAIGN_KEY) ?? "");
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tokenValue, setTokenValue] = useState(getToken());
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" | "info" | "warning" } | null>(null);
  const campaignsResource = useResource(() => api.get<Paginated<Campaign>>("/campaigns?limit=200"), []);
  const campaigns = campaignsResource.data?.items ?? [];
  const activeCampaign = campaigns.find((campaign) => campaign.id === campaignId) ?? null;

  useEffect(() => {
    const handler = () => setPage(currentPage());
    window.addEventListener("hashchange", handler);
    if (!window.location.hash) window.location.hash = "dashboard";
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  useEffect(() => {
    if (campaigns.length && !campaigns.some((campaign) => campaign.id === campaignId)) {
      setCampaignId(campaigns[0].id);
      localStorage.setItem(CAMPAIGN_KEY, campaigns[0].id);
    }
  }, [campaigns, campaignId]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function selectCampaign(id: string) {
    setCampaignId(id);
    if (id) localStorage.setItem(CAMPAIGN_KEY, id);
    else localStorage.removeItem(CAMPAIGN_KEY);
  }

  function notify(message: string, tone: "success" | "error" | "info" | "warning" = "info") {
    setToast({ message, tone });
  }

  function saveSessionToken(event: FormEvent) {
    event.preventDefault();
    setToken(tokenValue);
    setTokenOpen(false);
    campaignsResource.reload();
    notify(tokenValue ? "Session token saved" : "Session token cleared", "success");
  }

  const context = useMemo(
    () => ({
      campaigns,
      campaignId,
      activeCampaign,
      selectCampaign,
      refreshCampaigns: campaignsResource.reload,
      notify
    }),
    [campaigns, campaignId, activeCampaign, campaignsResource.reload]
  );
  const Screen = pages[page];

  return (
    <AppContext.Provider value={context}>
      <div className="app-shell">
        <aside className="sidebar">
          <a href="#dashboard" className="brand" aria-label="off_CRM home">
            <span className="brand-symbol">OX</span>
            <span><strong>off_CRM</strong><small>Your outreach, your data</small></span>
          </a>
          <nav aria-label="Main navigation">
            {navigation.map((item) => (
              <div key={item.page}>
                {item.group ? <p className="nav-group">{item.group}</p> : null}
                <a className={page === item.page ? "nav-active" : ""} href={`#${item.page}`}>
                  <span className={`nav-icon nav-icon-${item.page}`}>{item.icon}</span>
                  <span>{item.label}</span>
                  {item.page === "drafts" && campaignsResource.data ? <small className="nav-count">Review</small> : null}
                </a>
              </div>
            ))}
          </nav>
          <div className="sidebar-footer">
            <span className="local-dot" />
            <div><strong>Local workspace</strong><small>SQLite on this device</small></div>
          </div>
        </aside>
        <div className="app-main">
          <header className="topbar">
            <div className="campaign-switcher">
              <span>Campaign</span>
              <select value={campaignId} onChange={(event) => selectCampaign(event.target.value)} aria-label="Active campaign">
                {!campaigns.length ? <option value="">No campaign</option> : null}
                {campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
              </select>
              {activeCampaign ? <span className={`status-dot status-${activeCampaign.status}`} title={activeCampaign.status} /> : null}
            </div>
            <div className="topbar-actions">
              {campaignsResource.error ? <button className="connection-error" onClick={() => setTokenOpen(true)}>API access needed</button> : <span className="connection-ok"><span />Backend ready</span>}
              {auth.configured ? <span className="session-user">{auth.username}</span> : <button className="topbar-button" onClick={() => setTokenOpen(true)} aria-label="Set local API token">Key</button>}
              {auth.configured ? <button className="topbar-button logout-button" onClick={onLogout}>Log out</button> : null}
              <a className="topbar-button" href="/api/docs" target="_blank" rel="noreferrer" aria-label="Open API documentation">?</a>
            </div>
          </header>
          <nav className="mobile-nav" aria-label="Mobile navigation">
            {navigation.map((item) => <a key={item.page} className={page === item.page ? "nav-active" : ""} href={`#${item.page}`}><span>{item.icon}</span>{item.label}</a>)}
          </nav>
          <main className="page-content"><Screen /></main>
        </div>
      </div>
      {toast ? <div className={`toast toast-${toast.tone}`} role="status"><span>{toast.tone === "success" ? "✓" : toast.tone === "error" ? "!" : "i"}</span>{toast.message}<button onClick={() => setToast(null)} aria-label="Dismiss notification">×</button></div> : null}
      <Modal open={tokenOpen} onClose={() => setTokenOpen(false)} title="Local API token" description="Only needed if OFFSETX_LOCAL_API_TOKEN is enabled in the backend.">
        <form className="form-stack" onSubmit={saveSessionToken}>
          <Field label="Token"><input type="password" value={tokenValue} onChange={(event) => setTokenValue(event.target.value)} autoComplete="off" autoFocus /></Field>
          <div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setTokenOpen(false)}>Cancel</Button><Button type="submit">Save for session</Button></div>
        </form>
      </Modal>
    </AppContext.Provider>
  );
}

const EMPTY_AUTH: AuthSession = { configured: false, authenticated: false, username: "", expires_at: null };

export default function App() {
  const [auth, setAuth] = useState<AuthSession | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.get<AuthSession>("/auth/session")
      .then((session) => { if (active) setAuth(session); })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Backend unavailable"); });
    const requireLogin = () => setAuth((current) => current?.configured ? { ...current, authenticated: false, username: "" } : current);
    window.addEventListener(AUTH_REQUIRED_EVENT, requireLogin);
    return () => { active = false; window.removeEventListener(AUTH_REQUIRED_EVENT, requireLogin); };
  }, []);

  async function logout() {
    try {
      await api.post("/auth/logout", {});
    } finally {
      setToken("");
      setAuth({ ...EMPTY_AUTH, configured: true });
    }
  }

  if (error) {
    return <main className="login-shell"><section className="login-card"><h1>CRM unavailable</h1><p className="login-error">{error}</p><Button onClick={() => window.location.reload()}>Retry</Button></section></main>;
  }
  if (!auth) {
    return <main className="login-shell"><div className="spinner spinner-large" aria-label="Loading CRM" /></main>;
  }
  if (auth.configured && !auth.authenticated) {
    return <LoginScreen onLogin={setAuth} />;
  }
  return <AuthenticatedApp auth={auth} onLogout={logout} />;
}
