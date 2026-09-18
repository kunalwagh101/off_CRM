import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, Button, Field, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import type { CompanionProfile, CompanionsPayload } from "../types";
import { Loadable } from "./shared";

const EMPTY_TOOLS: string[] = [];

export default function Companions() {
  const { notify } = useApp();
  const resource = useResource(() => api.get<CompanionsPayload>("/ai/companions"), []);
  const [editing, setEditing] = useState<CompanionProfile | null>(null);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [memoryScope, setMemoryScope] = useState("global");
  const [grantedTools, setGrantedTools] = useState<string[]>(EMPTY_TOOLS);
  const [enabled, setEnabled] = useState(true);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!editing) return;
    setName(editing.name);
    setInstructions(editing.instructions);
    setMemoryScope(editing.memory_scope);
    setGrantedTools(editing.granted_tools);
    setEnabled(editing.enabled);
  }, [editing]);

  function reset() {
    setEditing(null);
    setName("");
    setInstructions("");
    setMemoryScope("global");
    setGrantedTools([]);
    setEnabled(true);
  }

  function toggleTool(tool: string) {
    setGrantedTools((current) =>
      current.includes(tool) ? current.filter((item) => item !== tool) : [...current, tool]
    );
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("save");
    const payload = {
      name: name.trim(),
      instructions: instructions.trim(),
      memory_scope: memoryScope.trim(),
      granted_tools: grantedTools,
      enabled
    };
    try {
      if (editing) {
        await api.patch(`/ai/companions/${editing.id}`, payload);
        notify(`${payload.name} updated`, "success");
      } else {
        await api.post("/ai/companions", payload);
        notify(`${payload.name} created`, "success");
      }
      reset();
      resource.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save companion", "error");
    } finally {
      setBusy("");
    }
  }

  async function setActive(profile: CompanionProfile, next: boolean) {
    setBusy(`toggle-${profile.id}`);
    try {
      await api.patch(`/ai/companions/${profile.id}`, { enabled: next });
      notify(`${profile.name} ${next ? "enabled" : "disabled"}`, "success");
      resource.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not update companion", "error");
    } finally {
      setBusy("");
    }
  }

  async function remove(profile: CompanionProfile) {
    if (!window.confirm(`Delete companion "${profile.name}"? Existing run traces stay intact.`)) return;
    setBusy(`delete-${profile.id}`);
    try {
      await api.delete(`/ai/companions/${profile.id}`);
      if (editing?.id === profile.id) reset();
      notify(`${profile.name} deleted`, "success");
      resource.reload();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not delete companion", "error");
    } finally {
      setBusy("");
    }
  }

  const data = resource.data;

  return (
    <div className="page-stack">
      <PageHeader
        title="Companions"
        description="Named agents with one instruction set, one memory scope and an explicit browser-tool grant. The runner enforces the grant; this screen does not create a second execution path."
      />

      <Panel
        title={editing ? `Edit ${editing.name}` : "New companion"}
        subtitle="Memory is data, not instructions. Browser tools are default-deny."
        className="settings-wide"
      >
        <form className="form-stack" onSubmit={save}>
          <div className="form-grid">
            <Field label="Name">
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                minLength={2}
                maxLength={80}
                required
                placeholder="Scout"
              />
            </Field>
            <Field label="Memory scope" hint="Exactly one existing memory scope, for example global or campaign:acme.">
              <input
                value={memoryScope}
                onChange={(event) => setMemoryScope(event.target.value)}
                maxLength={200}
                required
              />
            </Field>
          </div>

          <Field
            label="Owner instructions"
            hint="These are trusted instructions. Memory contents are injected separately as local data."
          >
            <textarea
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              rows={5}
              maxLength={8000}
              placeholder="Research first. Cite evidence. Never submit a form."
            />
          </Field>

          <fieldset className="form-stack">
            <legend>Granted browser tools</legend>
            <p className="form-note">Anything unchecked is refused even if the model asks for it.</p>
            <div className="button-row">
              {(data?.browser_tools ?? []).map((tool) => (
                <label key={tool} className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={grantedTools.includes(tool)}
                    onChange={() => toggleTool(tool)}
                  />
                  <span>{tool}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="checkbox-row">
            <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
            <span>Enabled for new runs</span>
          </label>

          <div className="button-row">
            <Button type="submit" busy={busy === "save"} disabled={!name.trim() || !memoryScope.trim()}>
              {editing ? "Save changes" : "Create companion"}
            </Button>
            {editing ? <Button type="button" tone="ghost" onClick={reset}>Cancel</Button> : null}
          </div>
        </form>
      </Panel>

      <Panel title="Saved companions" subtitle="Profiles are persisted locally and scoped to the current workspace." className="settings-wide">
        {resource.loading || resource.error ? (
          <Loadable loading={resource.loading} error={resource.error ?? ""} />
        ) : !data || data.items.length === 0 ? (
          <StatePanel
            title="No companion yet"
            description="Create one above. An empty tool grant is valid and means the agent can observe the prompt but cannot act in the browser."
          />
        ) : (
          <div className="task-list">
            {data.items.map((profile) => (
              <article key={profile.id} className="task-card">
                <header>
                  <strong>{profile.name}</strong>
                  <Badge tone={profile.enabled ? "success" : "neutral"}>
                    {profile.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </header>
                <p className="muted-copy">Memory: {profile.memory_scope}</p>
                <p>{profile.instructions || "No additional owner instructions."}</p>
                <p className="form-note">
                  Browser tools: {profile.granted_tools.length ? profile.granted_tools.join(", ") : "none"}
                </p>
                <div className="button-row">
                  <Button tone="ghost" onClick={() => setEditing(profile)}>Edit</Button>
                  <Button
                    tone="ghost"
                    busy={busy === `toggle-${profile.id}`}
                    onClick={() => setActive(profile, !profile.enabled)}
                  >
                    {profile.enabled ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    tone="ghost"
                    busy={busy === `delete-${profile.id}`}
                    onClick={() => remove(profile)}
                  >
                    Delete
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
