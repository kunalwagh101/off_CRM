import { useState } from "react";
import { api } from "../api";
import { Badge, Button, Panel, StatCard, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";

type Recalled = {
  message_id: string;
  subject: string;
  body: string;
  template_id: string;
  variant_id: string;
  stage: string;
  category: string;
  got_reply: boolean;
  sent_at: string;
};

type Overview = {
  stats: {
    indexed: number;
    replied: number;
    newest: string;
    searchable_locally: boolean;
    embeddings_used: boolean;
    stored_redacted: boolean;
    max_snippets_per_payload: number;
  };
  recent: Recalled[];
};

type Preview = {
  data_class: string;
  data_policy: string;
  used: Recalled[];
  payload: Record<string, unknown>;
  scan: { clean: boolean; findings: Array<{ kind: string; detail: string }> };
};

/**
 * Past emails, searchable.
 *
 * Two things this screen has to make obvious, because they are the reason the
 * feature is safe rather than a detail of it: searching happens on this machine
 * and sends nothing anywhere, and the copy that is stored already has the names
 * taken out. So the preview button shows the real payload, not a description of
 * one — the owner can read exactly what an AI would receive before it goes.
 */
export default function Recall() {
  const { notify } = useApp();
  const [query, setQuery] = useState("");
  const [repliedOnly, setRepliedOnly] = useState(false);
  const [results, setResults] = useState<Recalled[] | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState("");

  const overview = useResource(() => api.get<Overview>("/ai/recall"), []);
  const data = overview.data;

  async function search() {
    if (!query.trim()) return;
    setBusy("search");
    setPreview(null);
    try {
      const result = await api.post<{ results: Recalled[] }>("/ai/recall/search", {
        query,
        replied_only: repliedOnly,
        limit: 10
      });
      setResults(result.results);
      if (result.results.length === 0) notify("Nothing matched those words.", "warning");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Search failed", "error");
    } finally {
      setBusy("");
    }
  }

  async function showPreview() {
    setBusy("preview");
    try {
      setPreview(
        await api.post<Preview>("/ai/recall/preview", { query, replied_only: repliedOnly })
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not build the preview", "error");
    } finally {
      setBusy("");
    }
  }

  async function rebuild() {
    setBusy("rebuild");
    try {
      const result = await api.post<{ indexed: number }>("/ai/recall/rebuild", {});
      notify(`${result.indexed} sent emails are now searchable.`, "success");
      overview.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not rebuild", "error");
    } finally {
      setBusy("");
    }
  }

  async function forgetEverything() {
    if (!window.confirm("Remove every past email from the search index?")) return;
    setBusy("forget");
    try {
      const result = await api.post<{ removed: number }>("/ai/recall/forget", { everything: true });
      notify(`${result.removed} removed.`, "success");
      setResults(null);
      setPreview(null);
      overview.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not clear", "error");
    } finally {
      setBusy("");
    }
  }

  const shown = results ?? data?.recent ?? [];

  return (
    <div className="page-stack">
      <div className="page-header">
        <div>
          <h1>Past emails</h1>
          <p className="muted-copy">
            Search the emails you have already sent, and reuse the ones that worked.
          </p>
        </div>
        <div className="button-row">
          <Button tone="ghost" busy={busy === "rebuild"} onClick={rebuild}>
            Index old emails
          </Button>
        </div>
      </div>

      {/* The safety story, stated plainly and first. */}
      <Panel title="How this stays private" className="settings-wide">
        <ul className="plain-list">
          <li>
            <strong>Searching happens on this computer.</strong> No AI is contacted. No key is
            used. It costs nothing and works with the internet off.
          </li>
          <li>
            <strong>The saved copy has the names taken out already.</strong> Names, companies,
            email addresses, phone numbers and links are removed <em>before</em> anything is
            saved — so the file on disk has nothing to leak.
          </li>
          <li>
            <strong>Replies you received are never saved here.</strong> Only mail you sent. If a
            reply is quoted at the bottom of your follow-up, that part is cut off first.
          </li>
          <li>
            <strong>No AI can search this.</strong> off_CRM does the search and hands over the
            result. An AI has no way to ask for anything.
          </li>
        </ul>
      </Panel>

      {data ? (
        <div className="stat-row">
          <StatCard label="Emails searchable" value={String(data.stats.indexed)} />
          <StatCard label="Got a reply" value={String(data.stats.replied)} accent="green" />
          <StatCard label="Names stored" value="0" accent="violet" />
          <StatCard
            label="Sent to an AI to index"
            value="0"
            accent="blue"
          />
        </div>
      ) : null}

      <Panel title="Search" className="settings-wide">
        <div className="recall-search">
          <input
            className="model-filter"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") search();
            }}
            placeholder="What was the email about? e.g. customs evidence"
            aria-label="Search past emails"
          />
          <Button busy={busy === "search"} onClick={search} disabled={!query.trim()}>
            Search
          </Button>
        </div>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={repliedOnly}
            onChange={(event) => setRepliedOnly(event.target.checked)}
          />
          Only show emails that got a reply
        </label>

        {shown.length === 0 ? (
          <StatePanel
            title="Nothing here yet"
            description="Once you send emails they appear here. Already sent some? Press “Index old emails”."
          />
        ) : (
          <>
            <p className="form-note">
              {results ? `${shown.length} found` : "Most recent"} · showing the saved copy, with
              names already removed
            </p>
            <div className="task-list">
              {shown.map((item) => (
                <article key={item.message_id} className="task-card">
                  <header>
                    <strong>{item.subject || "(no subject)"}</strong>
                    {item.got_reply ? <Badge tone="success">Got a reply</Badge> : null}
                  </header>
                  <p className="recall-body">{item.body.slice(0, 400)}</p>
                  <small className="muted-copy">
                    {item.stage} · {item.variant_id || "—"} · {item.sent_at.slice(0, 10)}
                  </small>
                </article>
              ))}
            </div>
          </>
        )}
      </Panel>

      {/* Reading the real payload beats being told about it. */}
      {shown.length > 0 ? (
        <Panel
          title="What an AI would get"
          subtitle="The real message, built the same way a live call builds it"
          className="settings-wide"
        >
          <Button tone="ghost" busy={busy === "preview"} onClick={showPreview}>
            Show me exactly what would be sent
          </Button>

          {preview ? (
            <>
              <div className="preview-facts">
                <span>
                  Kind of data: <strong>{preview.data_class}</strong>
                </span>
                <span>
                  Setting: <strong>{preview.data_policy}</strong>
                </span>
                <span>
                  Safety check:{" "}
                  {preview.scan.clean ? (
                    <Badge tone="success">Clean</Badge>
                  ) : (
                    <Badge tone="danger">Blocked</Badge>
                  )}
                </span>
              </div>
              <p className="form-note">
                This counts as <strong>campaign</strong> material, not public. So an AI on the
                restricted list never receives it, and even a trusted one only receives it when
                its setting is “standard” or higher.
              </p>
              <pre className="payload-block">{JSON.stringify(preview.payload, null, 2)}</pre>
              {!preview.scan.clean ? (
                <ul className="plain-list">
                  {preview.scan.findings.map((finding, index) => (
                    <li key={index}>
                      <strong>{finding.kind}</strong>: {finding.detail}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
        </Panel>
      ) : null}

      <Panel title="Delete" subtitle="Removing the name is not the same as deleting the record">
        <Button tone="danger" busy={busy === "forget"} onClick={forgetEverything}>
          Remove every past email from search
        </Button>
        <p className="form-note">
          This only clears the search index. Your real emails and CRM records are untouched.
        </p>
      </Panel>
    </div>
  );
}
