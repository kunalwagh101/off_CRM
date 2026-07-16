import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, getToken, setToken } from "./api";
import { Button, Field, Modal } from "./components";
import { AppContext } from "./context";
import { useResource } from "./hooks";
import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import Contacts from "./pages/Contacts";
import Drafts from "./pages/Drafts";
import Queue from "./pages/Queue";
import Experiments from "./pages/Experiments";
import Settings from "./pages/Settings";
import type { Campaign, Paginated } from "./types";

const CAMPAIGN_KEY = "offsetx-active-campaign";
const pages = {
  dashboard: Dashboard,
  campaigns: Campaigns,
  contacts: Contacts,
  drafts: Drafts,
  queue: Queue,
  experiments: Experiments,
  settings: Settings
};
type Page = keyof typeof pages;

const navigation: Array<{ page: Page; label: string; icon: string; group?: string }> = [
  { page: "dashboard", label: "Overview", icon: "⌂", group: "Workspace" },
  { page: "campaigns", label: "Campaigns", icon: "◫" },
  { page: "contacts", label: "Contacts", icon: "◎" },
  { page: "drafts", label: "Draft review", icon: "✎", group: "Outreach" },
  { page: "queue", label: "Send queue", icon: "➤" },
  { page: "experiments", label: "Experiments", icon: "A/B" },
  { page: "settings", label: "Settings", icon: "⚙", group: "System" }
];

function currentPage(): Page {
  const value = window.location.hash.replace(/^#\/?/, "") as Page;
  return value in pages ? value : "dashboard";
}

export default function App() {
  const [page, setPage] = useState<Page>(currentPage());
  const [campaignId, setCampaignId] = useState(localStorage.getItem(CAMPAIGN_KEY) ?? "");
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tokenValue, setTokenValue] = useState(getToken());
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" | "info" } | null>(null);
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

  function notify(message: string, tone: "success" | "error" | "info" = "info") {
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
          <a href="#dashboard" className="brand" aria-label="OffsetX home">
            <span className="brand-symbol">OX</span>
            <span><strong>OffsetX</strong><small>Outreach OS</small></span>
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
              <button className="topbar-button" onClick={() => setTokenOpen(true)} aria-label="Set local API token">Key</button>
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
