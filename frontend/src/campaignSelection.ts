import { ApiError } from "./api";
import type { Campaign } from "./types";

export type CampaignSnapshot = {
  campaigns: Campaign[];
  campaignId: string;
  ready: boolean;
  loading: boolean;
  error: string;
  storageWarning: string;
  selectionNotice: string;
};

type CampaignSource = {
  list: () => Promise<Campaign[]>;
  get: (id: string) => Promise<Campaign>;
  create: (body: Record<string, unknown>) => Promise<Campaign>;
};

type SelectionStorage = { read: () => string; write: (id: string) => void };

const STORAGE_WARNING = "Browser storage is unavailable. Your campaign is selected for this tab; select it again after reloading.";

/** One snapshot owns both the list and its selection: they cannot disagree for a render. */
export class CampaignSelection {
  private snapshot: CampaignSnapshot = {
    campaigns: [], campaignId: "", ready: false, loading: true, error: "", storageWarning: "", selectionNotice: ""
  };
  private listeners = new Set<() => void>();
  private wantedId = "";
  private request = 0;
  private choice = 0;
  private active = true;
  private connection = 0;

  constructor(private source: CampaignSource, private storage: SelectionStorage) {
    try {
      this.wantedId = storage.read();
    } catch {
      this.snapshot.storageWarning = STORAGE_WARNING;
    }
  }

  getSnapshot = (): CampaignSnapshot => this.snapshot;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  connect = (): void => {
    this.active = true;
    void this.refresh();
  };

  disconnect = (): void => {
    this.active = false;
    this.connection++;
    this.request++;
    this.choice++;
  };

  private publish(next: CampaignSnapshot): void {
    this.snapshot = next;
    this.listeners.forEach((listener) => listener());
  }

  private commit(campaigns: Campaign[], campaignId: string, selectionNotice = ""): void {
    this.wantedId = campaignId;
    let storageWarning = "";
    try {
      this.storage.write(campaignId);
    } catch {
      storageWarning = STORAGE_WARNING;
    }
    this.publish({ campaigns, campaignId, ready: true, loading: false, error: "", storageWarning, selectionNotice });
  }

  refresh = async (): Promise<void> => {
    if (!this.active) return;
    const request = ++this.request;
    const wantedId = this.wantedId;
    const current = () => this.active && request === this.request;
    this.publish({ ...this.snapshot, loading: true, error: "" });
    try {
      let campaigns = await this.source.list();
      if (!current()) return;
      if (wantedId && !campaigns.some((campaign) => campaign.id === wantedId)) {
        // A bounded list is not evidence of deletion. Only the detail endpoint's
        // 404 permits a fallback; a timeout, denied request or 500 preserves intent.
        try {
          const selected = await this.source.get(wantedId);
          if (!current()) return;
          campaigns = [...campaigns, selected];
        } catch (error) {
          if (!current()) return;
          if (!(error instanceof ApiError && error.status === 404)) throw error;
        }
      }
      if (!current()) return;
      const selected = campaigns.find((campaign) => campaign.id === wantedId) ?? campaigns[0];
      const notice = wantedId && selected?.id !== wantedId
        ? (selected ? `The previous campaign is no longer available. Switched to ${selected.name}.` : "The previous campaign is no longer available. Create or select a campaign to continue.")
        : this.snapshot.selectionNotice;
      this.commit(campaigns, selected?.id ?? "", notice);
    } catch (error) {
      if (current()) this.publish({
        ...this.snapshot, loading: false,
        error: error instanceof Error ? error.message : "Could not load campaigns. Try again."
      });
    }
  };

  select = (id: string): void => {
    if (!this.active || !this.snapshot.campaigns.some((campaign) => campaign.id === id)) return;
    // Invalidate synchronously, before an older promise can commit its answer.
    this.request++;
    this.choice++;
    this.commit(this.snapshot.campaigns, id);
  };

  create = async (body: Record<string, unknown>): Promise<Campaign> => {
    const choice = ++this.choice;
    const connection = this.connection;
    const campaign = await this.source.create(body);
    if (!this.active || connection !== this.connection) return campaign;
    this.request++;
    const campaigns = [campaign, ...this.snapshot.campaigns.filter((item) => item.id !== campaign.id)];
    // A user switching campaign while the POST is pending has made a newer
    // choice. Keep that choice, while still displaying the successfully saved row.
    const selected = choice === this.choice ? campaign.id : (this.snapshot.campaignId || campaigns[0].id);
    this.commit(campaigns, selected);
    // A failed refresh cannot turn a successful save into "creation failed".
    void this.refresh();
    return campaign;
  };
}
