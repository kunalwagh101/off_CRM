import { useState } from "react";
import { api } from "../api";
import { Badge, Button, PageHeader, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { EgressLogEntry, EgressLogRow, EgressStats, Paginated } from "../types";
import { Loadable } from "./shared";

const TIER_TONE: Record<string, string> = { A: "success", B: "neutral", C: "warning", D: "danger" };

const STATUS_TONE: Record<string, string> = {
  succeeded: "success",
  blocked: "danger",
  failed: "warning"
};

const DATA_CLASS_WORD: Record<string, string> = {
  public: "Public content",
  person_public: "A person's public details",
  campaign: "Template and campaign",
  internal: "CRM records",
  mailbox: "Mailbox content"
};

/**
 * The screen that makes the promise checkable. Every outbound call is here,
 * with the exact payload — so "no provider sees your mailbox" is something the
 * owner can verify rather than take on trust.
 */
export default function Egress() {
  const { notify } = useApp();
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<EgressLogEntry | null>(null);
  const [loadingEntry, setLoadingEntry] = useState("");

  const stats = useResource(() => api.get<EgressStats>("/ai/egress-log/stats"), []);
  const log = useResource(
    () =>
      api.get<Paginated<EgressLogRow>>(
        `/ai/egress-log?limit=100${statusFilter ? `&status=${statusFilter}` : ""}`
      ),
    [statusFilter]
  );

  async function open(row: EgressLogRow) {
    setLoadingEntry(row.id);
    try {
      setSelected(await api.get<EgressLogEntry>(`/ai/egress-log/${row.id}`));
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not open this record", "error");
    } finally {
      setLoadingEntry("");
    }
  }

  const rows = log.data?.items ?? [];

  return (
    <div className="page-stack">
      <PageHeader
        title="What was sent"
        description="Every call off_CRM has made to an AI provider, and the exact payload that left. Nothing reaches a provider without appearing here first."
      />

      {stats.data ? (
        <div className="stat-row">
          <StatCard label="Calls made" value={String(stats.data.calls)} />
          <StatCard
            label="Blocked before sending"
            value={String(stats.data.blocked)}
            accent={stats.data.blocked > 0 ? "orange" : "blue"}
          />
          <StatCard label="Failed" value={String(stats.data.failed)} />
        </div>
      ) : null}

      {stats.data && stats.data.blocked > 0 ? (
        <Panel title="Blocked calls need a look" subtitle="A block means a payload carried something it should not">
          <p className="muted-copy">
            off_CRM stopped {stats.data.blocked} call{stats.data.blocked === 1 ? "" : "s"} because the payload
            contained something on the never-send list. Nothing was sent. Open the record below to see what was
            found — a block usually means a field needs fixing, not that you did anything wrong.
          </p>
          <Button tone="ghost" onClick={() => setStatusFilter("blocked")}>
            Show only blocked calls
          </Button>
        </Panel>
      ) : null}

      <Panel
        title="Call history"
        subtitle={rows.length ? `${log.data?.total ?? rows.length} recorded` : undefined}
        className="settings-wide"
      >
        <div className="filter-row" role="group" aria-label="Filter by outcome">
          {[
            { value: "", label: "All" },
            { value: "succeeded", label: "Sent" },
            { value: "blocked", label: "Blocked" },
            { value: "failed", label: "Failed" }
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              className={statusFilter === option.value ? "filter-chip filter-chip-on" : "filter-chip"}
              aria-pressed={statusFilter === option.value}
              onClick={() => setStatusFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>

        {log.loading || log.error ? (
          <Loadable loading={log.loading} error={log.error ?? ""} />
        ) : rows.length === 0 ? (
          <StatePanel
            title={statusFilter ? "Nothing matches this filter" : "No calls yet"}
            description={
              statusFilter
                ? "Try a different outcome, or clear the filter to see everything."
                : "Once you connect a provider and run AI work, every call will be listed here with the exact payload that left this machine."
            }
            action={
              statusFilter ? (
                <Button onClick={() => setStatusFilter("")}>Clear filter</Button>
              ) : (
                <Button onClick={() => (window.location.hash = "connectors")}>Open Connectors</Button>
              )
            }
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Provider</th>
                  <th scope="col">Country</th>
                  <th scope="col">Trust</th>
                  <th scope="col">What was sent</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">
                    <span className="visually-hidden">Inspect</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.created_at).toLocaleString()}</td>
                    <td>
                      <strong>{row.provider_name || row.provider_id}</strong>
                      <br />
                      <small className="muted-copy">{row.model_id}</small>
                    </td>
                    <td>{row.jurisdiction}</td>
                    <td>
                      <Badge tone={TIER_TONE[row.tier] ?? "neutral"}>{row.tier}</Badge>
                    </td>
                    <td>
                      {DATA_CLASS_WORD[row.data_class] ?? row.data_class}
                      <br />
                      <small className="muted-copy">{row.policy}</small>
                    </td>
                    <td>
                      <Badge tone={STATUS_TONE[row.status] ?? "neutral"}>{row.status}</Badge>
                    </td>
                    <td>
                      <Button tone="ghost" busy={loadingEntry === row.id} onClick={() => open(row)}>
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {selected ? <EgressDetail entry={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

function EgressDetail({ entry, onClose }: { entry: EgressLogEntry; onClose: () => void }) {
  return (
    <Panel
      title={`Sent to ${entry.provider_name || entry.provider_id}`}
      subtitle={`${entry.jurisdiction} · trust ${entry.tier} · ${entry.policy} · ${new Date(
        entry.created_at
      ).toLocaleString()}`}
      className="settings-wide"
    >
      {entry.status === "blocked" ? (
        <div className="egress-blocked">
          <strong>This call was stopped. Nothing was sent.</strong>
          <ul>
            {entry.findings.map((finding, index) => (
              <li key={index}>
                <code>{finding.kind}</code> — {finding.detail}
                {finding.sample ? (
                  <>
                    {" "}
                    <span className="muted-copy">({finding.sample})</span>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <h3 className="detail-heading">The exact payload that left</h3>
      <pre className="payload-block" aria-label="Payload sent to the provider">
        {JSON.stringify(entry.payload, null, 2)}
      </pre>

      {entry.response_text ? (
        <>
          <h3 className="detail-heading">What came back</h3>
          <pre className="payload-block">{entry.response_text}</pre>
        </>
      ) : null}

      {entry.error ? (
        <>
          <h3 className="detail-heading">Error</h3>
          <p className="form-note">{entry.error}</p>
        </>
      ) : null}

      <div className="button-row">
        <Button tone="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
    </Panel>
  );
}
