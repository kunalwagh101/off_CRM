import { useEffect, useMemo, useState, type FormEvent, useSyncExternalStore } from "react";
import { api, AUTH_REQUIRED_EVENT, getToken, setToken, idempotencyKey } from "./api";
import { Button, Field, Modal, StatePanel, StorageNote } from "./components";
import { AppContext } from "./context";
import { CampaignSelection } from "./campaignSelection";
import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import Contacts from "./pages/Contacts";
import LaunchReadiness from "./pages/LaunchReadiness";
import CampaignActivity from "./pages/CampaignActivity";
import ReplyInbox from "./pages/ReplyInbox";
import Followups from "./pages/Followups";
import ActionCenter from "./pages/ActionCenter";
import CRMSearch from "./pages/CRMSearch";
import AccountIntelligence from "./pages/AccountIntelligence";
import RevenueAttribution from "./pages/RevenueAttribution";
import { CRMDataQuality, CampaignComparison, FollowupPerformance } from "./pages/CRMOperations";
import Discovery from "./pages/Discovery";
import Drafts from "./pages/Drafts";
import Queue from "./pages/Queue";
import Deliverability from "./pages/Deliverability";
import SalesTracker from "./pages/SalesTracker";
import Experiments from "./pages/Experiments";
import ImageReview from "./pages/ImageReview";
import VideoEditor from "./pages/VideoEditor";
import Posting from "./pages/Posting";
import Product from "./pages/Product";
import Strategy from "./pages/Strategy";
import AI from "./pages/AI";
import Connectors from "./pages/Connectors";
import Egress from "./pages/Egress";
import Memory from "./pages/Memory";
import Meetings from "./pages/Meetings";
import Recall from "./pages/Recall";
import Settings from "./pages/Settings";
import { useResource } from "./hooks";
import type { AuthSession, Campaign, Paginated, SettingsStatus } from "./types";

const CAMPAIGN_KEY = "offsetx-active-campaign";
const pages = {
  dashboard: Dashboard,
  campaigns: Campaigns,
  discovery: Discovery,
  contacts: Contacts,
  readiness: LaunchReadiness,
  activity: CampaignActivity,
  replies: ReplyInbox,
  followups: Followups,
  priorities: ActionCenter,
  crmsearch: CRMSearch,
  accounts: AccountIntelligence,
  attribution: RevenueAttribution,
  crmquality: CRMDataQuality,
  campaigncompare: CampaignComparison,
  followupmetrics: FollowupPerformance,
  drafts: Drafts,
  queue: Queue,
  deliverability: Deliverability,
  sales: SalesTracker,
  experiments: Experiments,
  imagereview: ImageReview,
  videoeditor: VideoEditor,
  posting: Posting,
  product: Product,
  strategy: Strategy,
  connectors: Connectors,
  egress: Egress,
  memory: Memory,
  meetings: Meetings,
  recall: Recall,
  ai: AI,
  settings: Settings
};
type Page = keyof typeof pages;
// Screens that act on the selected campaign. Each remounts when the campaign
// changes, so a half-filled form cannot keep another campaign's rows (S-06.02.22).
const campaignScopedPages = new Set<Page>([
  "contacts", "discovery", "readiness", "activity", "replies", "followups", "priorities", "drafts", "queue", "deliverability", "experiments",
  "imagereview", "videoeditor", "posting", "settings"
]);
// Screens that read the campaign list or the selection, and so wait for its
// first load: before it, "No campaigns yet" would be untrue, and Product's
// checklist, saved from an empty list, would unlink its campaigns. The rest stay
// reachable when that load fails — which is when recovery is needed — Settings
// among them, where backup and restore live (D-130). Settings reads the
// selection too, but copes with none: its campaign export asks for one first.
export const campaignListPages = new Set<Page>([
  "dashboard", "campaigns", "product", "crmsearch", "accounts", "attribution", "crmquality", "campaigncompare", "followupmetrics",
  "contacts", "discovery", "readiness", "activity", "replies", "followups", "priorities", "drafts", "queue", "deliverability", "experiments",
  "imagereview", "videoeditor", "posting"
]);

const navigation: Array<{ page: Page; label: string; icon: string; group?: string }> = [
  { page: "ai", label: "AI", icon: "✦", group: "AI" },
  { page: "connectors", label: "Connectors", icon: "⚡" },
  { page: "egress", label: "What was sent", icon: "◉" },
  { page: "memory", label: "Memory", icon: "◈" },
  { page: "meetings", label: "Meetings", icon: "🎙" },
  { page: "recall", label: "Past emails", icon: "⟲" },
  { page: "dashboard", label: "Overview", icon: "⌂", group: "Workspace" },
  { page: "campaigns", label: "Campaigns", icon: "◫" },
  { page: "discovery", label: "Lead discovery", icon: "⌕" },
  { page: "contacts", label: "Contacts", icon: "◎" },
  { page: "readiness", label: "Launch readiness", icon: "✓" },
  { page: "activity", label: "Campaign activity", icon: "◷" },
  { page: "replies", label: "Reply inbox", icon: "↩" },
  { page: "followups", label: "Human follow-ups", icon: "☷" },
  { page: "priorities", label: "Today’s priorities", icon: "⚑" },
  { page: "crmsearch", label: "Unified CRM search", icon: "⌕" },
  { page: "accounts", label: "Company accounts", icon: "▦" },
  { page: "attribution", label: "Revenue attribution", icon: "↗" },
  { page: "crmquality", label: "CRM data quality", icon: "◎" },
  { page: "campaigncompare", label: "Compare campaigns", icon: "▤" },
  { page: "followupmetrics", label: "Follow-up performance", icon: "◷" },
  { page: "product", label: "Product", icon: "◆", group: "Strategy" },
  { page: "strategy", label: "Go-to-market plan", icon: "⌖" },
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

export function focusMainContent() {
  window.requestAnimationFrame(() => {
    const main = document.getElementById("main-content");
    if (!main) return;
    // Focus must not tuck the screen under the sticky navigation bar.
    main.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  });
}

export function skipToMainContent(event: { preventDefault(): void }) {
  // Our route is stored in the hash. Following "#main-content" as a native
  // anchor would change the route to Dashboard before focus could complete.
  event.preventDefault();
  focusMainContent();
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

export function AuthenticatedApp({ auth, onLogout }: { auth: AuthSession; onLogout: () => void }) {
  const [page, setPage] = useState<Page>(currentPage());
  // One store owns the campaign list and the selection, so they cannot
  // disagree for a render — which is how a new campaign lost its selection to
  // an older one when the stale list arrived first (audit A33, S-06.02.22).
  const [selection] = useState(() => new CampaignSelection({
    list: async () => (await api.get<Paginated<Campaign>>("/campaigns?limit=200")).items,
    get: (id) => api.get<Campaign>(`/campaigns/${encodeURIComponent(id)}`),
    create: (body) => api.post<Campaign>("/campaigns", body, idempotencyKey("campaign"))
  }, {
    read: () => localStorage.getItem(CAMPAIGN_KEY) ?? "",
    write: (id) => {
      if (id) localStorage.setItem(CAMPAIGN_KEY, id);
      else localStorage.removeItem(CAMPAIGN_KEY);
    }
  }));
  const campaignsResource = useSyncExternalStore(selection.subscribe, selection.getSnapshot, selection.getSnapshot);
  const { campaigns, campaignId } = campaignsResource;
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tokenValue, setTokenValue] = useState(getToken());
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" | "info" | "warning" } | null>(null);
  const activeCampaign = campaigns.find((campaign) => campaign.id === campaignId) ?? null;
  const storageStatus = useResource(() => api.get<SettingsStatus>("/settings/status"), []);

  useEffect(() => {
    const handler = () => setPage(currentPage());
    window.addEventListener("hashchange", handler);
    if (!window.location.hash) window.location.hash = "dashboard";
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  useEffect(() => {
    focusMainContent();
  }, [page]);

  useEffect(() => {
    selection.connect();
    return selection.disconnect;
  }, [selection]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function notify(message: string, tone: "success" | "error" | "info" | "warning" = "info") {
    setToast({ message, tone });
  }

  function saveSessionToken(event: FormEvent) {
    event.preventDefault();
    setToken(tokenValue);
    setTokenOpen(false);
    void selection.refresh();
    notify(tokenValue ? "Session token saved" : "Session token cleared", "success");
  }

  const context = useMemo(
    () => ({
      campaigns,
      campaignId,
      activeCampaign,
      selectCampaign: selection.select,
      createCampaign: selection.create,
      refreshCampaigns: selection.refresh,
      notify
    }),
    [campaigns, campaignId, activeCampaign, selection]
  );
  const Screen = pages[page];

  return (
    <AppContext.Provider value={context}>
      <a className="skip-link" href="#main-content" onClick={skipToMainContent}>Skip to main content</a>
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
                <a
                  className={page === item.page ? "nav-active" : ""}
                  href={`#${item.page}`}
                  aria-current={page === item.page ? "page" : undefined}
                >
                  <span className={`nav-icon nav-icon-${item.page}`} aria-hidden="true">{item.icon}</span>
                  <span>{item.label}</span>
                  {item.page === "drafts" && campaignsResource.ready ? <small className="nav-count">Review</small> : null}
                </a>
              </div>
            ))}
          </nav>
          <div className="sidebar-footer">
            <span className="local-dot" aria-hidden="true" />
            <StorageNote storage={storageStatus.data?.storage} />
          </div>
        </aside>
        <div className="app-main">
          <header className="topbar">
            <div className="campaign-switcher">
              <span>Campaign</span>
              <select value={campaignId} onChange={(event) => selection.select(event.target.value)} aria-label="Active campaign" disabled={!campaignsResource.ready}>
                {!campaigns.length ? <option value="">{campaignsResource.loading ? "Loading campaigns…" : "No campaign"}</option> : null}
                {campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
              </select>
              {activeCampaign ? (
                <>
                  <span className={`status-dot status-${activeCampaign.status}`} aria-hidden="true" />
                  <span className="sr-only">Campaign status: {activeCampaign.status}</span>
                </>
              ) : null}
            </div>
            <div className="topbar-actions">
              {campaignsResource.error ? (campaignsResource.authError ? <button className="connection-error" onClick={() => setTokenOpen(true)}>API access needed</button> : <span className="connection-error" role="status">Backend error</span>) : <span className="connection-ok"><span />Backend ready</span>}
              {auth.configured ? <span className="session-user">{auth.username}</span> : <button className="topbar-button" onClick={() => setTokenOpen(true)} aria-label="Set local API token">Key</button>}
              {auth.configured ? <button className="topbar-button logout-button" onClick={onLogout}>Log out</button> : null}
              <a className="topbar-button" href="/api/docs" target="_blank" rel="noreferrer" aria-label="Open API documentation">?</a>
            </div>
          </header>
          <nav className="mobile-nav" aria-label="Mobile navigation">
            {navigation.map((item) => (
              <a
                key={item.page}
                className={page === item.page ? "nav-active" : ""}
                href={`#${item.page}`}
                aria-current={page === item.page ? "page" : undefined}
              >
                <span aria-hidden="true">{item.icon}</span>{item.label}
              </a>
            ))}
          </nav>
          <main id="main-content" className="page-content" tabIndex={-1} aria-label="Main content">
            {campaignsResource.storageWarning ? <p className="form-note" role="alert">{campaignsResource.storageWarning}</p> : null}
            {campaignsResource.selectionNotice ? <p className="form-note" role="status">{campaignsResource.selectionNotice}</p> : null}
            {campaignsResource.error ? <StatePanel title="Could not refresh campaigns" description={campaignsResource.error + (campaignsResource.ready ? " Your current selection has been kept." : " Retry before starting campaign work.")} action={<Button onClick={() => void selection.refresh()} busy={campaignsResource.loading}>Retry campaigns</Button>} /> : null}
            {!campaignsResource.ready && campaignsResource.loading && campaignListPages.has(page) ? <div className="spinner spinner-large" role="status" aria-label="Loading campaigns" /> : null}
            {campaignsResource.ready || !campaignListPages.has(page) ? <Screen key={campaignScopedPages.has(page) ? `${page}:${campaignId}` : page} /> : null}
          </main>
        </div>
      </div>
      {toast ? (
        <div
          className={`toast toast-${toast.tone}`}
          role={toast.tone === "error" ? "alert" : "status"}
          aria-live={toast.tone === "error" ? "assertive" : "polite"}
        >
          <span aria-hidden="true">{toast.tone === "success" ? "✓" : toast.tone === "error" ? "!" : "i"}</span>
          {toast.message}
          <button onClick={() => setToast(null)} aria-label="Dismiss notification">×</button>
        </div>
      ) : null}
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
