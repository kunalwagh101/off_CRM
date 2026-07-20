import { useMemo, useState, type DragEvent, type FormEvent, type KeyboardEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Badge, Button, Field, Modal, PageHeader, Panel, StatePanel, StatCard } from "../components";
import { useApp } from "../context";
import { formatDate, useResource } from "../hooks";
import type {
  CloserMetric,
  Paginated,
  SalesBoard,
  SalesDashboard,
  SalesLead,
  SalesLeadStatus,
  SalesMeta,
  SalesProjection,
  SetterMetric
} from "../types";
import { Loadable } from "./shared";

type SalesView = "board" | "log" | "dashboard" | "projection";
type LeadDraft = SalesLead | null;

const LEAK_LABELS = {
  booking_lag: "Booking lag >4d",
  follow_up_aging: "No touch 7+d",
  deposit_unpaid: "Deposit unpaid 14+d"
};

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function currentDate(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function toLocalInput(value?: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value.slice(0, 16);
  const local = new Date(parsed.valueOf() - parsed.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoOrNull(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const parsed = new Date(text);
  return Number.isNaN(parsed.valueOf()) ? null : parsed.toISOString();
}

function numberValue(value: FormDataEntryValue | null): number {
  const parsed = Number(String(value ?? "").trim() || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatSalesMoney(value: number, currency = "INR"): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0
  }).format(value || 0);
}

function percentage(value: number): string {
  return `${Number(value || 0).toFixed(value % 1 ? 1 : 0)}%`;
}

function buildQuery(values: Record<string, string>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params.toString();
}

function leadInitials(lead: SalesLead): string {
  return lead.lead_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "LD";
}

function statusTone(status: SalesLeadStatus): string {
  if (status === "won") return "success";
  if (status === "lost") return "danger";
  if (status === "deposit" || status === "proposal") return "blue";
  if (status.includes("follow_up")) return "warning";
  return "neutral";
}

function LeadEditor({
  lead,
  meta,
  busy,
  onCancel,
  onSave
}: {
  lead: LeadDraft;
  meta: SalesMeta;
  busy: boolean;
  onCancel: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [status, setStatus] = useState<SalesLeadStatus>(lead?.lead_status ?? "new");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {
      lead_name: String(data.get("lead_name") ?? "").trim(),
      company: String(data.get("company") ?? "").trim(),
      email: String(data.get("email") ?? "").trim(),
      phone: String(data.get("phone") ?? "").trim(),
      source: String(data.get("source") ?? "").trim(),
      setter_name: String(data.get("setter_name") ?? "").trim(),
      closer_name: String(data.get("closer_name") ?? "").trim(),
      lead_status: status,
      date_created: toIsoOrNull(data.get("date_created")),
      first_contact_at: toIsoOrNull(data.get("first_contact_at")),
      date_meeting_booked: toIsoOrNull(data.get("date_meeting_booked")),
      meeting_at: toIsoOrNull(data.get("meeting_at")),
      meeting_status: String(data.get("meeting_status") ?? ""),
      offer_made: data.get("offer_made") === "on",
      sale_type: String(data.get("sale_type") ?? ""),
      loss_reason: status === "lost" ? String(data.get("loss_reason") ?? "") : "",
      deposit_amount: numberValue(data.get("deposit_amount")),
      deposit_received_at: toIsoOrNull(data.get("deposit_received_at")),
      total_deal_value: numberValue(data.get("total_deal_value")),
      cash_collected: numberValue(data.get("cash_collected")),
      date_paid_in_full: toIsoOrNull(data.get("date_paid_in_full")),
      refund_clawback_amount: numberValue(data.get("refund_clawback_amount")),
      commission_percent: numberValue(data.get("commission_percent")),
      last_touch_at: toIsoOrNull(data.get("last_touch_at")),
      notes: String(data.get("notes") ?? "")
    };
    if (lead) payload.expected_revision = lead.revision;
    await onSave(payload);
  }

  return (
    <form className="sales-lead-form form-stack" onSubmit={submit}>
      <section className="lead-form-section">
        <div className="lead-form-heading"><span>01</span><div><strong>Contact</strong><small>Core lead ownership and source</small></div></div>
        <div className="form-grid three-up">
          <Field label="Lead name"><input name="lead_name" defaultValue={lead?.lead_name} required autoFocus /></Field>
          <Field label="Company"><input name="company" defaultValue={lead?.company} /></Field>
          <Field label="Lead status"><select name="lead_status" value={status} onChange={(event) => setStatus(event.target.value as SalesLeadStatus)}>{meta.statuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>
        </div>
        <div className="form-grid three-up">
          <Field label="Email"><input name="email" type="email" defaultValue={lead?.email} /></Field>
          <Field label="Phone #"><input name="phone" type="tel" defaultValue={lead?.phone} /></Field>
          <Field label="Source"><input name="source" list="sales-sources" defaultValue={lead?.source} /><datalist id="sales-sources">{meta.sources.map((item) => <option key={item} value={item} />)}</datalist></Field>
        </div>
        <div className="form-grid">
          <Field label="Setter name"><input name="setter_name" list="sales-setters" defaultValue={lead?.setter_name} /><datalist id="sales-setters">{meta.setters.map((item) => <option key={item} value={item} />)}</datalist></Field>
          <Field label="Closer name"><input name="closer_name" list="sales-closers" defaultValue={lead?.closer_name} /><datalist id="sales-closers">{meta.closers.map((item) => <option key={item} value={item} />)}</datalist></Field>
        </div>
      </section>

      <section className="lead-form-section">
        <div className="lead-form-heading"><span>02</span><div><strong>Dates & meeting</strong><small>Used automatically for speed, lag and show metrics</small></div></div>
        <div className="form-grid three-up">
          <Field label="Date created"><input name="date_created" type="datetime-local" defaultValue={toLocalInput(lead?.date_created) || toLocalInput(new Date().toISOString())} required /></Field>
          <Field label="First contact"><input name="first_contact_at" type="datetime-local" defaultValue={toLocalInput(lead?.first_contact_at)} /></Field>
          <Field label="Date meeting booked"><input name="date_meeting_booked" type="datetime-local" defaultValue={toLocalInput(lead?.date_meeting_booked)} /></Field>
        </div>
        <div className="form-grid three-up">
          <Field label="Date of meeting"><input name="meeting_at" type="datetime-local" defaultValue={toLocalInput(lead?.meeting_at)} /></Field>
          <Field label="Meeting status"><select name="meeting_status" defaultValue={lead?.meeting_status ?? ""}>{meta.meeting_statuses.map((option) => <option key={option.value || "empty"} value={option.value}>{option.label}</option>)}</select></Field>
          <Field label="Last touch date"><input name="last_touch_at" type="datetime-local" defaultValue={toLocalInput(lead?.last_touch_at)} /></Field>
        </div>
      </section>

      <section className="lead-form-section">
        <div className="lead-form-heading"><span>03</span><div><strong>Call outcome</strong><small>Feeds closer performance automatically</small></div></div>
        <div className="form-grid three-up">
          <label className="check-card"><input name="offer_made" type="checkbox" defaultChecked={lead?.offer_made} /><span><strong>Offer made</strong><small>Include this call in offer-rate math</small></span></label>
          <Field label="Sale type"><select name="sale_type" defaultValue={lead?.sale_type ?? ""}>{meta.sale_types.map((option) => <option key={option.value || "empty"} value={option.value}>{option.label}</option>)}</select></Field>
          {status === "lost" ? <Field label="Loss reason"><select name="loss_reason" defaultValue={lead?.loss_reason ?? ""} required><option value="">Select a reason</option>{meta.loss_reasons.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field> : <div className="form-note compact-note"><strong>Loss capture</strong><span>A reason becomes required only when moved to Lost.</span></div>}
        </div>
      </section>

      <section className="lead-form-section">
        <div className="lead-form-heading"><span>04</span><div><strong>Money</strong><small>Earnings and net revenue are calculated—not re-entered</small></div></div>
        <div className="form-grid three-up">
          <Field label="Deposit amount"><input name="deposit_amount" type="number" min="0" step="0.01" defaultValue={lead?.deposit_amount ?? 0} /></Field>
          <Field label="Deposit received"><input name="deposit_received_at" type="datetime-local" defaultValue={toLocalInput(lead?.deposit_received_at)} /></Field>
          <Field label="Total deal value"><input name="total_deal_value" type="number" min="0" step="0.01" defaultValue={lead?.total_deal_value ?? 0} required={status === "won"} /></Field>
        </div>
        <div className="form-grid three-up">
          <Field label="Cash collected"><input name="cash_collected" type="number" min="0" step="0.01" defaultValue={lead?.cash_collected ?? 0} /></Field>
          <Field label="Date paid in full"><input name="date_paid_in_full" type="datetime-local" defaultValue={toLocalInput(lead?.date_paid_in_full)} /></Field>
          <Field label="Refund / clawback"><input name="refund_clawback_amount" type="number" min="0" step="0.01" defaultValue={lead?.refund_clawback_amount ?? 0} /></Field>
        </div>
        <div className="form-grid">
          <Field label="Commission %" hint="Earnings = (deal value − refund/clawback) × commission %"><input name="commission_percent" type="number" min="0" max="100" step="0.01" defaultValue={lead?.commission_percent ?? 0} /></Field>
          <div className="calculation-card"><span>Auto-calculated earnings</span><strong>{formatSalesMoney(lead?.earnings ?? 0)}</strong><small>Recalculated immediately after save</small></div>
        </div>
      </section>

      <Field label="Internal notes"><textarea name="notes" rows={4} defaultValue={lead?.notes} placeholder="Context, objections, next step…" /></Field>
      <div className="modal-actions sticky-actions"><Button type="button" tone="ghost" onClick={onCancel}>Cancel</Button><Button type="submit" busy={busy}>{lead?.id ? "Save lead" : "Create lead"}</Button></div>
    </form>
  );
}

function SalesFilters({
  meta,
  rep,
  source,
  startDate,
  endDate,
  search,
  onRep,
  onSource,
  onStartDate,
  onEndDate,
  onSearch,
  onClear
}: {
  meta: SalesMeta | null;
  rep: string;
  source: string;
  startDate: string;
  endDate: string;
  search: string;
  onRep: (value: string) => void;
  onSource: (value: string) => void;
  onStartDate: (value: string) => void;
  onEndDate: (value: string) => void;
  onSearch: (value: string) => void;
  onClear: () => void;
}) {
  const active = rep || source || startDate || endDate || search;
  return (
    <div className="sales-filterbar" aria-label="Sales filters">
      <div className="sales-search"><span aria-hidden="true">⌕</span><input aria-label="Search sales leads" placeholder="Search leads, companies, email…" value={search} onChange={(event) => onSearch(event.target.value)} /></div>
      <select aria-label="Filter by representative" value={rep} onChange={(event) => onRep(event.target.value)}><option value="">All reps</option>{meta?.reps.map((item) => <option key={item} value={item}>{item}</option>)}</select>
      <select aria-label="Filter by source" value={source} onChange={(event) => onSource(event.target.value)}><option value="">All sources</option>{meta?.sources.map((item) => <option key={item} value={item}>{item}</option>)}</select>
      <label><span>From</span><input type="date" value={startDate} onChange={(event) => onStartDate(event.target.value)} /></label>
      <label><span>To</span><input type="date" value={endDate} onChange={(event) => onEndDate(event.target.value)} /></label>
      {active ? <button className="filter-clear" onClick={onClear}>Clear</button> : null}
    </div>
  );
}

function LeakStrip({ leaks }: { leaks?: SalesBoard["leaks"] | SalesDashboard["leaks"] }) {
  if (!leaks?.total) return <div className="leak-strip leak-clear"><span>✓</span><strong>No active sales leaks in this view</strong></div>;
  return (
    <div className="leak-strip" role="status">
      <span>!</span><strong>{leaks.total} leads need attention</strong>
      <small>{leaks.booking_lag} booking lag</small><small>{leaks.follow_up_aging} aging follow-ups</small><small>{leaks.deposit_unpaid} unpaid deposits</small>
    </div>
  );
}

function SalesCard({
  lead,
  meta,
  currency,
  onEdit,
  onMove,
  onDragStart
}: {
  lead: SalesLead;
  meta: SalesMeta;
  currency: string;
  onEdit: () => void;
  onMove: (status: SalesLeadStatus) => void;
  onDragStart: (event: DragEvent<HTMLElement>) => void;
}) {
  function keyEdit(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onEdit();
    }
  }
  return (
    <article className={`sales-card ${lead.leak_flags.length ? "sales-card-leak" : ""}`} draggable onDragStart={onDragStart} onClick={onEdit} onKeyDown={keyEdit} tabIndex={0} aria-label={`Edit ${lead.lead_name}`}>
      <div className="sales-card-head"><span className="sales-avatar">{leadInitials(lead)}</span><div><strong>{lead.lead_name}</strong><small>{lead.company || "No company"}</small></div><span className="drag-handle" title="Drag to move">⠿</span></div>
      <div className="sales-card-meta"><span>{lead.source || "Direct"}</span>{lead.setter_name ? <span>S · {lead.setter_name}</span> : null}{lead.closer_name ? <span>C · {lead.closer_name}</span> : null}</div>
      {lead.meeting_at ? <div className={`sales-card-line ${lead.booking_lag_alert ? "danger-text" : ""}`}><span>Meeting</span><strong>{formatDate(lead.meeting_at)}</strong></div> : null}
      {lead.total_deal_value > 0 ? <div className="sales-card-money"><span>Deal</span><strong>{formatSalesMoney(lead.total_deal_value, currency)}</strong><small>{formatSalesMoney(lead.cash_collected, currency)} collected</small></div> : null}
      {lead.leak_flags.length ? <div className="leak-tags">{lead.leak_flags.map((flag) => <span key={flag}>{LEAK_LABELS[flag]}</span>)}</div> : null}
      <div className="card-status-control" onClick={(event) => event.stopPropagation()}>
        <select aria-label={`Move ${lead.lead_name}`} value={lead.lead_status} onChange={(event) => onMove(event.target.value as SalesLeadStatus)}>{meta.statuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
        <span>Rev {lead.revision}</span>
      </div>
    </article>
  );
}

function SetterTable({ rows }: { rows: SetterMetric[] }) {
  return (
    <div className="table-wrap"><table className="metrics-table"><thead><tr><th>Setter</th><th>Dials / DMs</th><th>Conversations</th><th>Conv → booked</th><th>Speed to lead</th><th>Booking lag</th><th>Scheduled</th><th>Taken</th><th>Declines</th><th>Cancels</th><th>No-shows</th><th>Show rate</th><th>DQ rate</th></tr></thead><tbody>{rows.map((row) => <tr key={row.rep_name}><td><strong>{row.rep_name}</strong></td><td>{row.dials_dms_sent}</td><td>{row.conversations}</td><td>{percentage(row.conversations_to_booked_rate)}</td><td>{row.speed_to_lead_minutes} min</td><td className={row.booking_lag_days > 4 ? "metric-danger" : ""}>{row.booking_lag_days} d</td><td>{row.calls_scheduled}</td><td>{row.calls_taken}</td><td>{row.declines}</td><td>{row.cancels}</td><td>{row.no_shows}</td><td>{percentage(row.show_up_rate)}</td><td>{percentage(row.dq_rate)}</td></tr>)}</tbody></table></div>
  );
}

function CloserTable({ rows, currency }: { rows: CloserMetric[]; currency: string }) {
  return (
    <div className="table-wrap"><table className="metrics-table"><thead><tr><th>Closer</th><th>Calls</th><th>Offers</th><th>Offer rate</th><th>Sales</th><th>Close / calls</th><th>Close / offers</th><th>1-call</th><th>Follow-up</th><th>Avg deal</th><th>RPC</th><th>Aging follow-ups</th></tr></thead><tbody>{rows.map((row) => <tr key={row.rep_name}><td><strong>{row.rep_name}</strong></td><td>{row.calls_taken}</td><td>{row.offers_made}</td><td>{percentage(row.offer_rate)}</td><td>{row.sales}</td><td>{percentage(row.close_rate)}</td><td>{percentage(row.close_rate_on_offers)}</td><td>{row.one_call_sales}</td><td>{row.follow_up_sales}</td><td>{formatSalesMoney(row.average_deal_size, currency)}</td><td>{formatSalesMoney(row.revenue_per_call, currency)}</td><td className={row.follow_up_aging ? "metric-danger" : ""}>{row.follow_up_aging}</td></tr>)}</tbody></table></div>
  );
}

export default function SalesTracker() {
  const { notify } = useApp();
  const [view, setView] = useState<SalesView>("board");
  const [rep, setRep] = useState("");
  const [source, setSource] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [search, setSearch] = useState("");
  const [logStatus, setLogStatus] = useState("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [editor, setEditor] = useState<LeadDraft | undefined>(undefined);
  const [activityOpen, setActivityOpen] = useState(false);
  const [goalOpen, setGoalOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draggedId, setDraggedId] = useState("");
  const [projectionRequest, setProjectionRequest] = useState<Record<string, unknown>>({ forecast_month: currentMonth() });

  const meta = useResource(() => api.get<SalesMeta>("/sales/meta"), []);
  const commonQuery = useMemo(() => buildQuery({ rep_name: rep, source, start_date: startDate, end_date: endDate, search }), [rep, source, startDate, endDate, search]);
  const board = useResource(() => api.get<SalesBoard>(`/sales/board?${commonQuery}`), [commonQuery]);
  const leadLog = useResource(
    () => api.get<Paginated<SalesLead>>(`/sales/leads?${buildQuery({ rep_name: rep, source, start_date: startDate, end_date: endDate, search, status: logStatus, sort_by: sortBy, sort_direction: sortDirection, limit: "5000" })}`),
    [rep, source, startDate, endDate, search, logStatus, sortBy, sortDirection]
  );
  const dashboard = useResource(
    () => api.get<SalesDashboard>(`/sales/dashboard?${buildQuery({ rep_name: rep, source, start_date: startDate, end_date: endDate, search, goal_month: (endDate || currentDate()).slice(0, 7) })}`),
    [rep, source, startDate, endDate, search]
  );
  const projectionKey = JSON.stringify(projectionRequest);
  const projection = useResource(() => api.post<SalesProjection>("/sales/projection", projectionRequest), [projectionKey]);

  const allBoardLeads = useMemo(() => board.data?.columns.flatMap((column) => column.items) ?? [], [board.data]);
  const currency = dashboard.data?.money.currency ?? meta.data?.currency_default ?? "INR";

  function clearFilters() {
    setRep(""); setSource(""); setStartDate(""); setEndDate(""); setSearch("");
  }

  function refreshAll() {
    meta.reload(); board.reload(); leadLog.reload(); dashboard.reload(); projection.reload();
  }

  async function saveLead(payload: Record<string, unknown>) {
    setBusy(true);
    try {
      if (editor?.id) await api.patch<SalesLead>(`/sales/leads/${editor.id}`, payload);
      else await api.post<SalesLead>("/sales/leads", payload, idempotencyKey("sales-lead"));
      notify(editor?.id ? "Lead updated and every downstream metric recalculated." : "Lead created on the sales board.", "success");
      setEditor(undefined);
      refreshAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Lead could not be saved", "error");
    } finally {
      setBusy(false);
    }
  }

  async function moveLead(lead: SalesLead, target: SalesLeadStatus) {
    if (lead.lead_status === target) return;
    if ((target === "lost" && !lead.loss_reason) || (target === "won" && lead.total_deal_value <= 0)) {
      setEditor({ ...lead, lead_status: target });
      notify(target === "lost" ? "Choose a loss reason before moving this card to Lost." : "Add the deal value before moving this card to Won.", "info");
      return;
    }
    try {
      await api.post(`/sales/leads/${lead.id}/move`, { lead_status: target, expected_revision: lead.revision });
      notify(`${lead.lead_name} moved to ${meta.data?.statuses.find((item) => item.value === target)?.label ?? target}.`, "success");
      refreshAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Card could not be moved", "error");
      refreshAll();
    }
  }

  async function saveActivity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await api.post("/sales/activity", {
        activity_date: data.get("activity_date"),
        setter_name: data.get("setter_name"),
        dials_dms_sent: numberValue(data.get("dials_dms_sent")),
        conversations: numberValue(data.get("conversations")),
        declines: numberValue(data.get("declines")),
        notes: data.get("notes")
      });
      notify("Setter activity saved. Dashboard metrics recalculated.", "success");
      setActivityOpen(false); refreshAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Activity could not be saved", "error");
    } finally { setBusy(false); }
  }

  async function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const month = String(data.get("month") || currentMonth());
    setBusy(true);
    try {
      await api.patch(`/sales/goals/${month}`, {
        revenue_goal: numberValue(data.get("revenue_goal")),
        cash_goal: numberValue(data.get("cash_goal")),
        currency: String(data.get("currency") || "INR").toUpperCase()
      });
      notify("Monthly goal updated.", "success"); setGoalOpen(false); refreshAll();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Goal could not be saved", "error");
    } finally { setBusy(false); }
  }

  function runProjection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const optionalNumber = (name: string) => {
      const value = String(data.get(name) ?? "").trim();
      return value === "" ? undefined : Number(value);
    };
    setProjectionRequest({
      forecast_month: String(data.get("forecast_month") || currentMonth()),
      history_start: String(data.get("history_start") || "") || undefined,
      history_end: String(data.get("history_end") || "") || undefined,
      rep_name: String(data.get("rep_name") || ""),
      source: String(data.get("source") || ""),
      meetings_scheduled: optionalNumber("meetings_scheduled"),
      show_up_rate: optionalNumber("show_up_rate"),
      offer_rate: optionalNumber("offer_rate"),
      close_rate: optionalNumber("close_rate"),
      average_deal_size: optionalNumber("average_deal_size"),
      cash_collection_rate: optionalNumber("cash_collection_rate")
    });
  }

  function changeSort(field: string) {
    if (sortBy === field) setSortDirection((value) => value === "asc" ? "desc" : "asc");
    else { setSortBy(field); setSortDirection("asc"); }
  }

  const filters = <SalesFilters meta={meta.data} rep={rep} source={source} startDate={startDate} endDate={endDate} search={search} onRep={setRep} onSource={setSource} onStartDate={setStartDate} onEndDate={setEndDate} onSearch={setSearch} onClear={clearFilters} />;

  return (
    <>
      <PageHeader eyebrow="Sales operating system" title="Sales tracker" description="Lead cards are the only source of truth. The log, team metrics, commissions, leak alerts and forecast recalculate automatically." actions={<><Button tone="secondary" onClick={() => setActivityOpen(true)}>Daily activity</Button><Button onClick={() => setEditor(null)}>+ New lead</Button></>} />
      <div className="sales-view-tabs" role="tablist" aria-label="Sales tracker views">
        {(["board", "log", "dashboard", "projection"] as SalesView[]).map((item) => <button key={item} role="tab" aria-selected={view === item} className={view === item ? "active" : ""} onClick={() => setView(item)}>{item === "board" ? "Kanban board" : item === "log" ? "Lead log" : item === "dashboard" ? "Visibility dashboard" : "Projection"}</button>)}
      </div>
      {view !== "projection" ? filters : null}

      {meta.loading || meta.error ? <Loadable loading={meta.loading} error={meta.error} /> : null}

      {view === "board" && meta.data ? (
        <>
          <LeakStrip leaks={board.data?.leaks} />
          {board.loading || board.error ? <Loadable loading={board.loading} error={board.error} /> : board.data?.total ? (
            <div className="kanban-scroll"><div className="sales-kanban">
              {board.data.columns.map((column) => (
                <section key={column.status} className={`kanban-column kanban-${column.status}`} onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }} onDrop={(event) => { event.preventDefault(); const id = event.dataTransfer.getData("text/plain") || draggedId; const lead = allBoardLeads.find((item) => item.id === id); if (lead) void moveLead(lead, column.status); setDraggedId(""); }}>
                  <header><div><span className="column-dot" /><strong>{column.label}</strong><small>{column.count}</small></div><span>{formatSalesMoney(column.pipeline_value, currency)}</span></header>
                  <div className="kanban-cards">{column.items.map((lead) => <SalesCard key={lead.id} lead={lead} meta={meta.data!} currency={currency} onEdit={() => setEditor(lead)} onMove={(status) => void moveLead(lead, status)} onDragStart={(event) => { setDraggedId(lead.id); event.dataTransfer.setData("text/plain", lead.id); event.dataTransfer.effectAllowed = "move"; }} />)}{!column.items.length ? <div className="kanban-empty">Drop a lead here</div> : null}</div>
                </section>
              ))}
            </div></div>
          ) : <StatePanel title="Your sales board is ready" description="Create the first lead card. Every log row, metric and projection will be derived from it." action={<Button onClick={() => setEditor(null)}>Create first lead</Button>} />}
        </>
      ) : null}

      {view === "log" && meta.data ? (
        <Panel className="sales-log-panel" title="Lead log" subtitle="All lead-card fields in one filterable, sortable operational ledger." action={<select aria-label="Filter log by status" value={logStatus} onChange={(event) => setLogStatus(event.target.value)}><option value="">All statuses</option>{meta.data.statuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>}>
          {leadLog.loading || leadLog.error ? <Loadable loading={leadLog.loading} error={leadLog.error} /> : leadLog.data?.items.length ? <div className="table-wrap sales-log-wrap"><table className="sales-log-table"><thead><tr><th><button onClick={() => changeSort("lead_name")}>Lead {sortBy === "lead_name" ? (sortDirection === "asc" ? "↑" : "↓") : ""}</button></th><th>Status</th><th>Ownership</th><th>Source</th><th><button onClick={() => changeSort("date_created")}>Created / contact</button></th><th><button onClick={() => changeSort("meeting_at")}>Meeting</button></th><th>Outcome</th><th><button onClick={() => changeSort("total_deal_value")}>Deal</button></th><th><button onClick={() => changeSort("cash_collected")}>Cash</button></th><th>Refund</th><th><button onClick={() => changeSort("earnings")}>Earnings</button></th><th><button onClick={() => changeSort("last_touch_at")}>Last touch</button></th><th>Leaks</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{leadLog.data.items.map((lead) => <tr key={lead.id} className={lead.leak_flags.length ? "leak-row" : ""}><td><button className="text-button" onClick={() => setEditor(lead)}>{lead.lead_name}</button><small>{lead.company || "No company"} · {lead.email || lead.phone || "No contact details"}</small>{lead.notes ? <small title={lead.notes}>{lead.notes.slice(0, 80)}{lead.notes.length > 80 ? "…" : ""}</small> : null}</td><td><Badge tone={statusTone(lead.lead_status)}>{lead.lead_status_label}</Badge>{lead.loss_reason ? <small>{lead.loss_reason_label}</small> : null}</td><td><strong>{lead.setter_name || "No setter"}</strong><small>{lead.closer_name || "No closer"}</small></td><td>{lead.source || "—"}</td><td>{formatDate(lead.date_created)}<small>{lead.first_contact_at ? `First touch ${formatDate(lead.first_contact_at)}` : "Not contacted"}</small></td><td>{formatDate(lead.meeting_at ?? undefined)}<small>{lead.meeting_status_label || "No disposition"}{lead.date_meeting_booked ? ` · booked ${formatDate(lead.date_meeting_booked)}` : ""}</small></td><td>{lead.offer_made ? "Offer made" : "No offer"}<small>{lead.sale_type_label || "No sale type"}</small></td><td>{formatSalesMoney(lead.total_deal_value, currency)}<small>Deposit {formatSalesMoney(lead.deposit_amount, currency)}</small></td><td>{formatSalesMoney(lead.cash_collected, currency)}<small>{lead.date_paid_in_full ? `PIF ${formatDate(lead.date_paid_in_full)}` : "Not paid in full"}</small></td><td>{formatSalesMoney(lead.refund_clawback_amount, currency)}</td><td><strong>{formatSalesMoney(lead.earnings, currency)}</strong><small>{lead.commission_percent}% commission</small></td><td>{formatDate(lead.last_touch_at ?? undefined)}</td><td>{lead.leak_flags.length ? <div className="leak-tags compact">{lead.leak_flags.map((flag) => <span key={flag}>{LEAK_LABELS[flag]}</span>)}</div> : <span className="healthy-mark">✓ Healthy</span>}</td><td><Button tone="ghost" onClick={() => setEditor(lead)}>Edit</Button></td></tr>)}</tbody></table></div> : <StatePanel title="No matching sales leads" description="Clear filters or create a lead card from the Kanban board." />}
        </Panel>
      ) : null}

      {view === "dashboard" ? (
        dashboard.loading || dashboard.error ? <Loadable loading={dashboard.loading} error={dashboard.error} /> : dashboard.data ? <div className="sales-dashboard">
          <LeakStrip leaks={dashboard.data.leaks} />
          <div className="sales-summary-grid"><StatCard label="Revenue generated" value={formatSalesMoney(dashboard.data.money.revenue_generated, currency)} detail={`${dashboard.data.money.total_sales} closed sales`} accent="blue" /><StatCard label="Cash collected" value={formatSalesMoney(dashboard.data.money.cash_collected, currency)} detail={`${percentage(dashboard.data.money.deposit_to_paid_in_full_rate)} deposits paid in full`} accent="green" /><StatCard label="Net revenue" value={formatSalesMoney(dashboard.data.money.net_revenue, currency)} detail={`${formatSalesMoney(dashboard.data.money.refunds_clawbacks, currency)} refunds / clawbacks`} accent="violet" /><StatCard label="Commissions earned" value={formatSalesMoney(dashboard.data.money.commissions_total, currency)} detail="Net of clawbacks" accent="orange" /></div>
          <Panel title="Revenue goal" subtitle={`${dashboard.data.money.goal_month} · ${dashboard.data.lead_count} leads in this view`} action={<Button tone="secondary" onClick={() => setGoalOpen(true)}>Edit goal</Button>}>
            <div className="goal-layout"><div><strong>{percentage(dashboard.data.money.goal_completion_percent)}</strong><span>complete</span></div><div className="goal-track"><span style={{ width: `${Math.min(100, dashboard.data.money.goal_completion_percent)}%` }} /><small>{formatSalesMoney(dashboard.data.money.revenue_generated, currency)} of {formatSalesMoney(dashboard.data.money.revenue_goal, currency)}</small></div><div><strong>{formatSalesMoney(dashboard.data.money.deposits, currency)}</strong><span>deposits</span></div><div><strong>{dashboard.data.money.average_days_to_collect} days</strong><span>avg. to collect</span></div></div>
          </Panel>
          <Panel title="Setter visibility" subtitle="Activity input plus scheduling outcomes derived from lead cards." action={<Button tone="secondary" onClick={() => setActivityOpen(true)}>Add daily activity</Button>}><SetterTable rows={[dashboard.data.setter_summary, ...dashboard.data.setter_metrics]} /></Panel>
          <Panel title="Closer visibility" subtitle="Offer, conversion and revenue efficiency derived from card outcomes."><CloserTable rows={[dashboard.data.closer_summary, ...dashboard.data.closer_metrics]} currency={currency} /></Panel>
          <div className="sales-dashboard-split">
            <Panel title="Why deals are lost" subtitle="Required whenever a card enters Lost."><div className="loss-chart">{dashboard.data.loss_reasons.map((item) => <div key={item.reason}><span>{item.label}</span><div><i style={{ width: `${item.percent}%` }} /></div><strong>{item.count} · {percentage(item.percent)}</strong></div>)}</div></Panel>
            <Panel title="Commission by closer" subtitle="(Won revenue − clawbacks) × commission %"><div className="commission-list">{dashboard.data.money.commissions_by_rep.length ? dashboard.data.money.commissions_by_rep.map((item) => <div key={item.rep_name}><span className="sales-avatar">{item.rep_name.slice(0, 2).toUpperCase()}</span><strong>{item.rep_name}</strong><b>{formatSalesMoney(item.earnings, currency)}</b></div>) : <StatePanel title="No commissions yet" description="Won cards with a commission percentage appear here." />}</div></Panel>
          </div>
        </div> : null
      ) : null}

      {view === "projection" ? <div className="projection-layout">
        <Panel title="Forecast assumptions" subtitle="Leave a field blank to use observed CRM performance. Manual overrides are visibly labelled.">
          <form className="form-stack" onSubmit={runProjection}>
            <div className="form-grid"><Field label="Forecast month"><input name="forecast_month" type="month" defaultValue={String(projectionRequest.forecast_month ?? currentMonth())} required /></Field><Field label="Meetings scheduled" hint="Blank = meetings currently on the board"><input name="meetings_scheduled" type="number" min="0" placeholder="Auto" /></Field></div>
            <div className="form-grid"><Field label="Historical period from"><input name="history_start" type="date" /></Field><Field label="Historical period to"><input name="history_end" type="date" /></Field></div>
            <div className="form-grid"><Field label="Representative"><select name="rep_name" defaultValue={rep}><option value="">All reps</option>{meta.data?.reps.map((item) => <option key={item} value={item}>{item}</option>)}</select></Field><Field label="Source"><select name="source" defaultValue={source}><option value="">All sources</option>{meta.data?.sources.map((item) => <option key={item} value={item}>{item}</option>)}</select></Field></div>
            <div className="form-grid three-up"><Field label="Show-up rate %"><input name="show_up_rate" type="number" min="0" max="100" step="0.1" placeholder="Auto" /></Field><Field label="Offer rate %"><input name="offer_rate" type="number" min="0" max="100" step="0.1" placeholder="Auto" /></Field><Field label="Close rate on offers %"><input name="close_rate" type="number" min="0" max="100" step="0.1" placeholder="Auto" /></Field></div>
            <div className="form-grid"><Field label="Average deal size"><input name="average_deal_size" type="number" min="0" step="0.01" placeholder="Auto" /></Field><Field label="Cash collection rate %"><input name="cash_collection_rate" type="number" min="0" max="100" step="0.1" placeholder="Auto" /></Field></div>
            <Button type="submit">Recalculate projection</Button>
          </form>
        </Panel>
        <div className="projection-results">
          {projection.loading || projection.error ? <Loadable loading={projection.loading} error={projection.error} /> : projection.data ? <>
            <div className="projection-current"><div><span>Revenue already won</span><strong>{formatSalesMoney(projection.data.current_revenue, projection.data.currency)}</strong></div><div><span>Cash already collected</span><strong>{formatSalesMoney(projection.data.current_cash, projection.data.currency)}</strong></div><small>{projection.data.forecast_month} forecast · performance history {projection.data.history_start} to {projection.data.history_end}</small></div>
            <div className="scenario-grid">{projection.data.scenarios.map((scenario) => <article key={scenario.name} className={`scenario-card scenario-${scenario.name}`}><Badge tone={scenario.name === "best" ? "success" : scenario.name === "worst" ? "danger" : "blue"}>{scenario.name} case</Badge><span>End-of-month revenue</span><strong>{formatSalesMoney(scenario.end_of_month_revenue, projection.data!.currency)}</strong><div><span>End-of-month cash <b>{formatSalesMoney(scenario.end_of_month_cash, projection.data!.currency)}</b></span><span>Projected sales <b>{scenario.projected_sales}</b></span><span>Shows / offers <b>{scenario.projected_shows} / {scenario.projected_offers}</b></span><span>Meetings modeled <b>{scenario.meetings}</b></span></div></article>)}</div>
            <Panel title="Forecast evidence" subtitle="Every assumption shows whether it came from history, current pipeline, a manual override or a conservative fallback."><div className="assumption-grid">{Object.entries(projection.data.assumptions).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{key.includes("rate") ? percentage(value) : key === "average_deal_size" ? formatSalesMoney(value, projection.data!.currency) : value}</strong><Badge tone={projection.data!.assumption_sources[key] === "manual" ? "violet" : projection.data!.assumption_sources[key] === "fallback" || projection.data!.assumption_sources[key] === "missing" ? "warning" : "success"}>{projection.data!.assumption_sources[key] ?? "pipeline"}</Badge></div>)}</div>{projection.data.defaults_used.length ? <p className="projection-warning">Limited history: conservative fallbacks used for {projection.data.defaults_used.join(", ").replaceAll("_", " ")}.</p> : null}</Panel>
          </> : null}
        </div>
      </div> : null}

      <Modal open={editor !== undefined} onClose={() => setEditor(undefined)} title={editor?.id ? `Edit ${editor.lead_name}` : "Create sales lead"} description="Save once; every downstream view and metric recalculates from this card." wide>
        {meta.data && editor !== undefined ? <LeadEditor key={`${editor?.id ?? "new"}-${editor?.lead_status ?? "new"}`} lead={editor} meta={meta.data} busy={busy} onCancel={() => setEditor(undefined)} onSave={saveLead} /> : null}
      </Modal>

      <Modal open={activityOpen} onClose={() => setActivityOpen(false)} title="Daily setter activity" description="One entry per setter per date. Saving the same date updates it instead of duplicating it.">
        <form className="form-stack" onSubmit={saveActivity}><div className="form-grid"><Field label="Activity date"><input name="activity_date" type="date" defaultValue={currentDate()} required /></Field><Field label="Setter name"><input name="setter_name" list="activity-setters" defaultValue={rep} required /><datalist id="activity-setters">{meta.data?.setters.map((item) => <option key={item} value={item} />)}</datalist></Field></div><div className="form-grid three-up"><Field label="Dials / DMs"><input name="dials_dms_sent" type="number" min="0" defaultValue="0" required /></Field><Field label="Conversations"><input name="conversations" type="number" min="0" defaultValue="0" required /></Field><Field label="Declines"><input name="declines" type="number" min="0" defaultValue="0" required /></Field></div><Field label="Notes"><textarea name="notes" rows={3} /></Field><div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setActivityOpen(false)}>Cancel</Button><Button type="submit" busy={busy}>Save activity</Button></div></form>
      </Modal>

      <Modal open={goalOpen} onClose={() => setGoalOpen(false)} title="Monthly sales goal" description="Revenue and cash completion update immediately from Won and collected card values.">
        <form className="form-stack" onSubmit={saveGoal}><div className="form-grid"><Field label="Month"><input name="month" type="month" defaultValue={dashboard.data?.money.goal_month ?? currentMonth()} required /></Field><Field label="Currency"><input name="currency" pattern="[A-Za-z]{3}" maxLength={3} defaultValue={currency} required /></Field></div><Field label="Revenue goal"><input name="revenue_goal" type="number" min="0" step="0.01" defaultValue={dashboard.data?.money.revenue_goal ?? 0} required /></Field><Field label="Cash goal"><input name="cash_goal" type="number" min="0" step="0.01" defaultValue={dashboard.data?.money.cash_goal ?? 0} required /></Field><div className="modal-actions"><Button type="button" tone="ghost" onClick={() => setGoalOpen(false)}>Cancel</Button><Button type="submit" busy={busy}>Save goal</Button></div></form>
      </Modal>
    </>
  );
}
