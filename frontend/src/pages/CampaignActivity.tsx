import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type { Paginated } from "../types";
import { Loadable, NoCampaign } from "./shared";

type CampaignEvent = {
  id: string;
  event_type: string;
  created_at: string;
  campaign_contact_id?: string | null;
  payload?: Record<string, unknown>;
};
type EventFacet = { event_type: string; count: number };
export const ACTIVITY_PAGE_SIZE = 50;

export function activityPath(campaignId: string, page: number, eventType: string): string {
  return `/campaigns/${encodeURIComponent(campaignId)}/events?limit=${ACTIVITY_PAGE_SIZE}&offset=${Math.max(0, page) * ACTIVITY_PAGE_SIZE}&event_type=${encodeURIComponent(eventType)}`;
}

const SAFE_DETAILS = ["action", "added", "changed", "requested", "approved", "blocked", "generated", "sent_count", "status", "fields", "reused_contact"];
export function safeEventDetails(event: CampaignEvent): string {
  const content = event.payload ?? {};
  return SAFE_DETAILS.flatMap((key) => {
    const value = content[key];
    if (typeof value === "boolean" || typeof value === "number") return [`${key.replaceAll("_", " ")}: ${String(value)}`];
    if (key === "action" && typeof value === "string" && ["mark", "unmark", "stop"].includes(value)) {
      return [`action: ${value}`];
    }
    if (key === "fields" && Array.isArray(value)) {
      const names = value.filter((item) => typeof item === "string" && /^[a-z_]{1,40}$/.test(item)).slice(0, 12);
      return names.length ? [`updated fields: ${names.join(", ")}`] : [];
    }
    return [];
  }).join(" · ");
}

export default function CampaignActivity() {
  const { campaignId, activeCampaign } = useApp();
  const [eventType, setEventType] = useState("");
  const [page, setPage] = useState(0);
  const facets = useResource(
    () => campaignId ? api.get<{ items: EventFacet[] }>(
      `/campaigns/${encodeURIComponent(campaignId)}/events/types`
    ) : Promise.resolve({ items: [] }),
    [campaignId]
  );
  const events = useResource(
    () => campaignId ? api.get<Paginated<CampaignEvent>>(
      activityPath(campaignId, page, eventType)
    ) : Promise.resolve({ items: [], total: 0 }),
    [campaignId, page, eventType]
  );
  const total = events.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / ACTIVITY_PAGE_SIZE));
  useEffect(() => {
    if (!events.loading && !events.error && events.data && page >= pages) setPage(pages - 1);
  }, [events.loading, events.error, events.data, page, pages]);
  if (!campaignId) return <><PageHeader title="Campaign activity" /><NoCampaign /></>;
  const state = <Loadable loading={events.loading} error={events.error} />;
  return <>
    <PageHeader eyebrow={activeCampaign?.name} title="Campaign activity"
      description="An audit-friendly timeline of recorded campaign operations. Private message bodies and raw event payloads are not displayed."
      actions={<Button tone="secondary" onClick={() => { facets.reload(); events.reload(); }}>Refresh history</Button>} />
    <Panel>
      <div className="toolbar">
        <label htmlFor="event-type">Event type</label>
        <select id="event-type" value={eventType} onChange={(e) => { setPage(0); setEventType(e.target.value); }}>
          <option value="">All events</option>
          {(facets.data?.items ?? []).map((f) => (
            <option key={f.event_type} value={f.event_type}>{f.event_type.replaceAll("_", " ")} ({f.count})</option>
          ))}
        </select>
        <span className="toolbar-count">{total} recorded events</span>
      </div>
      {events.loading || events.error ? state : events.data?.items.length ? (
        <ol aria-label="Campaign activity timeline" className="activity-timeline">
          {events.data.items.map((event) => (
            <li key={event.id}>
              <strong>{event.event_type.replaceAll("_", " ")}</strong>
              <small> · {formatDate(event.created_at)}</small>
              {safeEventDetails(event) && <p>{safeEventDetails(event)}</p>}
            </li>
          ))}
        </ol>
      ) : <StatePanel title="No events match this view"
        description="Change the event type or perform an operation in this campaign to see a recorded event." />}
      {!events.loading && !events.error && total > ACTIVITY_PAGE_SIZE && <nav className="toolbar" aria-label="Activity pages">
        <span>Showing {page * ACTIVITY_PAGE_SIZE + 1}–{Math.min(total, (page + 1) * ACTIVITY_PAGE_SIZE)} of {total}</span>
        <Button tone="ghost" disabled={page === 0} onClick={() => setPage(v => Math.max(0, v - 1))}>Previous page</Button>
        <Button tone="ghost" disabled={page + 1 >= pages} onClick={() => setPage(v => Math.min(pages - 1, v + 1))}>Next page</Button>
      </nav>}
    </Panel>
  </>;
}
