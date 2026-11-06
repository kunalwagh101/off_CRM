import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, idempotencyKey } from "../api";
import { Button, Field, Modal, PageHeader, Panel, StatePanel } from "../components";
import { useApp } from "../context";
import { useResource } from "../hooks";
import { Loadable } from "./shared";
import { ContextPreviewView, RoleResultView, DelegationResultView, type ContextPreview, type RoleOutcome, type DelegationOutcome } from "./AgentTeamResults";

export type Companion = { id: string; name: string; instructions: string; memory_scope: string; granted_tool_ids: string[]; enabled: boolean };
export type Procedure = { id: string; name: string; content: string; enabled: boolean };
type Named = { id: string; name: string };
type Tool = Named & { description: string };
type Account = { id: string; label: string; handle: string; enabled: number };
type Assignment = { companion_id: string; goal: string };
const ROLES = ["Scout", "Maker", "Poster", "Analyst", "Director"] as const;
type Role = typeof ROLES[number];
const describeError = (error: unknown) => error instanceof Error ? error.message : "The action failed. Retry after checking the workspace.";
const toggle = (items: string[], id: string) => items.includes(id) ? items.filter((v) => v !== id) : [...items, id];

export default function AgentTeam() {
  const { notify, campaigns, publicDemo, selectCampaign } = useApp();
  const session = useResource(() => api.get<{ workspace_id: string }>("/auth/session"), []);
  const owner = session.data?.workspace_id === "local" && !publicDemo;
  const profiles = useResource(() => api.get<{ items: Companion[] }>("/companions"), []);
  const skills = useResource(() => owner ? api.get<{ items: Procedure[] }>("/companion-skills") : Promise.resolve({ items: [] }), [owner]);
  const tools = useResource(() => api.get<{ items: Tool[] }>("/companion-tools"), []);
  const products = useResource(() => owner ? api.get<{ items: Named[] }>("/gtm/products") : Promise.resolve({ items: [] }), [owner]);
  const accounts = useResource(() => owner ? api.get<{ items: Account[] }>("/distribution/accounts") : Promise.resolve({ items: [] }), [owner]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  const [selected, setSelected] = useState("");
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [editName, setEditName] = useState("");
  const [editInstructions, setEditInstructions] = useState("");
  const [scope, setScope] = useState("");
  const [grants, setGrants] = useState<string[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [skillId, setSkillId] = useState("");
  const [skillName, setSkillName] = useState("");
  const [skillContent, setSkillContent] = useState("");
  const [context, setContext] = useState<ContextPreview | null>(null);
  const [message, setMessage] = useState("");
  const [memory, setMemory] = useState("");
  const [approved, setApproved] = useState(false);
  const [answer, setAnswer] = useState("");
  const [role, setRole] = useState<Role>("Scout");
  const [campaign, setCampaign] = useState("");
  const [imageCampaign, setImageCampaign] = useState("");
  const [topic, setTopic] = useState("");
  const [accountIds, setAccountIds] = useState<string[]>([]);
  const [product, setProduct] = useState("");
  const [target, setTarget] = useState(20);
  const [days, setDays] = useState(30);
  const [roleResult, setRoleResult] = useState<RoleOutcome | null>(null);
  const [resultCampaign, setResultCampaign] = useState("");
  const [assignments, setAssignments] = useState<Assignment[]>([{ companion_id: "", goal: "" }]);
  const [delegated, setDelegated] = useState<DelegationOutcome | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "profile" | "skill"; id: string; name: string } | null>(null);
  const profile = profiles.data?.items.find((p) => p.id === selected);
  const enabledProfiles = (profiles.data?.items ?? []).filter((p) => p.enabled);
  const roleCampaigns = campaigns.filter((c) => c.kind === (role === "Maker" ? "image" : "distribution"));
  useEffect(() => {
    if (campaign && !campaigns.some((c) => c.id === campaign && c.kind === (role === "Maker" ? "image" : "distribution"))) setCampaign("");
  }, [role, campaigns, campaign]);
  useEffect(() => {
    setEditName(profile?.name ?? ""); setEditInstructions(profile?.instructions ?? "");
    setScope(profile?.memory_scope ?? ""); setGrants(profile?.granted_tool_ids ?? []);
    setSelectedSkills([]); setContext(null); setAnswer(""); setDelegated(null);
    setAssignments([{ companion_id: "", goal: "" }]); setMemory(""); setApproved(false);
  }, [profile]);
  useEffect(() => {
    const enabled = new Set((skills.data?.items ?? []).filter((p) => p.enabled).map((p) => p.id));
    setSelectedSkills((current) => current.filter((id) => enabled.has(id)));
    setContext(null);
  }, [skills.data]);

  async function perform(label: string, action: () => Promise<void>) {
    setBusy(label); setError("");
    try { await action(); }
    catch (caught) { setError(describeError(caught)); }
    finally { setBusy(""); }
  }
  function submit(event: FormEvent, label: string, action: () => Promise<void>) {
    event.preventDefault(); void perform(label, action);
  }
  async function removeConfirmed() {
    if (!confirm) return;
    const removing = confirm;
    await perform("delete", async () => {
      await api.delete(`/${removing.kind === "profile" ? "companions" : "companion-skills"}/${encodeURIComponent(removing.id)}`);
      if (removing.kind === "profile") { setSelected(""); profiles.reload(); }
      else { setSelectedSkills((ids) => ids.filter((id) => id !== removing.id)); skills.reload(); }
      setContext(null); setConfirm(null);
    });
  }
  if (publicDemo) return <StatePanel title="Agent team needs an owner session" description="Sign in to your own installation to manage companions and procedures." />;
  return <>
    <PageHeader title="Agent team" description="Keep named companions, their approved memory and selected procedures together. Actions use your existing workspace settings." />
    <Loadable loading={profiles.loading || session.loading} error={profiles.error || session.error} />
    {(profiles.error || session.error) && <Button onClick={() => { profiles.reload(); session.reload(); }}>Retry loading</Button>}
    {error && <div role="alert" ref={errorRef} tabIndex={-1} className="danger-note">{error}</div>}
    {!owner && !session.loading && <p className="form-note">Profiles belong to this workspace. The install owner manages procedures, role actions and child reasoning.</p>}
    <fieldset disabled={Boolean(busy)} className="agent-team-workspace">
      <legend className="sr-only">Agent team controls</legend>
      <Panel title="Companion profiles">
        {owner && <Button tone="secondary" busy={busy === "provision"} onClick={() => void perform("provision", async () => {
          await api.post("/agent-team/provision", {}, idempotencyKey("team")); profiles.reload(); notify("Five roles are ready. Existing profiles were preserved.", "success");
        })}>Set up five roles</Button>}
        <form className="form-stack" onSubmit={(e) => submit(e, "create", async () => {
          const created = await api.post<Companion>("/companions", { name: name.trim(), instructions: instructions.trim(), granted_tool_ids: [] }, idempotencyKey("companion"));
          setName(""); setInstructions(""); profiles.reload(); setSelected(created.id); notify("Companion saved", "success");
        })}>
          <Field label="Profile name"><input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Profile instructions"><textarea required maxLength={12000} rows={3} value={instructions} onChange={(e) => setInstructions(e.target.value)} /></Field>
          <Button type="submit" busy={busy === "create"}>Create companion</Button>
        </form>
        <Field label="Companion"><select aria-label="Companion" value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">Select a companion</option>{(profiles.data?.items ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
        {profile && <form className="form-stack" onSubmit={(e) => submit(e, "save", async () => {
          await api.patch(`/companions/${encodeURIComponent(profile.id)}`, { name: editName.trim(), instructions: editInstructions.trim(), memory_scope: scope.trim(), granted_tool_ids: grants }); profiles.reload(); notify("Profile updated", "success");
        })}>
          <Field label="Edit profile name"><input required maxLength={100} value={editName} onChange={(e) => setEditName(e.target.value)} /></Field>
          <Field label="Edit profile instructions"><textarea required maxLength={12000} rows={3} value={editInstructions} onChange={(e) => setEditInstructions(e.target.value)} /></Field>
          <Field label="Memory scope" hint="Only approved facts in this exact scope enter the companion's context."><input required maxLength={160} value={scope} onChange={(e) => setScope(e.target.value)} /></Field>
          <fieldset><legend>Granted registered tools</legend><Loadable loading={tools.loading} error={tools.error} />{tools.error && <Button type="button" tone="secondary" onClick={tools.reload}>Retry tools</Button>}
            {(tools.data?.items ?? []).map((tool) => <label className="checkbox-row" key={tool.id}><input type="checkbox" checked={grants.includes(tool.id)} onChange={() => setGrants(toggle(grants, tool.id))} />{tool.name}</label>)}
            {!tools.loading && !tools.data?.items.length && <p>No enabled tools are registered in this workspace. No tool access is added by default.</p>}
          </fieldset>
          <div className="page-actions"><Button type="submit" busy={busy === "save"}>Save profile</Button><Button tone="secondary" type="button" onClick={() => void perform("enable", async () => { await api.patch(`/companions/${profile.id}`, { enabled: !profile.enabled }); profiles.reload(); })}>{profile.enabled ? "Disable companion" : "Enable companion"}</Button><Button tone="danger" type="button" onClick={() => setConfirm({ kind: "profile", id: profile.id, name: profile.name })}>Delete companion</Button></div>
        </form>}
      </Panel>
      {owner && <Panel title="Procedures">
        <Loadable loading={skills.loading} error={skills.error} />{skills.error && <Button onClick={skills.reload}>Retry procedures</Button>}
        <p>Only procedures you explicitly select enter a run. Select up to three; changing companions or reloading clears the selection.</p>
        <form className="form-stack" onSubmit={(e) => submit(e, "skill", async () => {
          if (skillId) await api.patch(`/companion-skills/${encodeURIComponent(skillId)}`, { name: skillName.trim(), content: skillContent.trim() });
          else await api.post("/companion-skills", { name: skillName.trim(), content: skillContent.trim() }, idempotencyKey("procedure"));
          setSkillId(""); setSkillName(""); setSkillContent(""); skills.reload(); notify("Procedure saved", "success");
        })}>
          <Field label="Procedure name"><input required maxLength={100} value={skillName} onChange={(e) => setSkillName(e.target.value)} /></Field>
          <Field label="Procedure text"><textarea required maxLength={2000} rows={3} value={skillContent} onChange={(e) => setSkillContent(e.target.value)} /></Field>
          <Button type="submit" busy={busy === "skill"}>{skillId ? "Save procedure" : "Create procedure"}</Button>{skillId && <Button type="button" tone="secondary" onClick={() => { setSkillId(""); setSkillName(""); setSkillContent(""); }}>Cancel procedure edit</Button>}
        </form>
        {(skills.data?.items ?? []).map((skill) => <div key={skill.id} className="agent-team-procedure">
          <label className="checkbox-row"><input type="checkbox" disabled={!profile?.enabled || !skill.enabled || (!selectedSkills.includes(skill.id) && selectedSkills.length >= 3)} checked={selectedSkills.includes(skill.id)} onChange={() => { setSelectedSkills(toggle(selectedSkills, skill.id)); setContext(null); }} />{skill.name}</label>
          <div className="page-actions"><Button tone="ghost" onClick={() => { setSkillId(skill.id); setSkillName(skill.name); setSkillContent(skill.content); }}>Edit {skill.name}</Button><Button tone="secondary" onClick={() => void perform("skill-toggle", async () => { await api.patch(`/companion-skills/${skill.id}`, { enabled: !skill.enabled }); skills.reload(); })}>{skill.enabled ? "Disable" : "Enable"} {skill.name}</Button><Button tone="danger" onClick={() => setConfirm({ kind: "skill", id: skill.id, name: skill.name })}>Delete {skill.name}</Button></div>
        </div>)}
      </Panel>}
      {profile && <Panel title="Context and approved memory">
        <Button disabled={!profile.enabled} onClick={() => void perform("preview", async () => { setContext(await api.post<ContextPreview>(`/companions/${profile.id}/context`, { skill_ids: selectedSkills, memory_limit: 8 })); })}>Preview selected context</Button>
        {context !== null && <ContextPreviewView value={context} />}
        <form className="form-stack" onSubmit={(e) => submit(e, "memory", async () => { await api.post(`/companions/${profile.id}/memory`, { content: memory.trim(), approved }, idempotencyKey("memory")); setMemory(""); setApproved(false); setContext(null); notify("Memory saved to this companion's scope", "success"); })}>
          <Field label="Companion fact"><textarea required maxLength={30000} rows={2} value={memory} onChange={(e) => setMemory(e.target.value)} /></Field>
          <label className="checkbox-row"><input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} />Approve this fact for future context</label><Button type="submit">Save scoped memory</Button>
        </form>
        <form className="form-stack" onSubmit={(e) => submit(e, "message", async () => {
          const chat = await api.post<{ id: string }>("/ai/chats", { title: profile.name }, idempotencyKey("companion-chat"));
          const reply = await api.post<{ content: string }>(`/ai/chats/${chat.id}/messages`, { content: message.trim(), companion_id: profile.id, skill_ids: selectedSkills, data_class: "campaign" }, idempotencyKey("companion-message"));
          setAnswer(reply.content); setMessage("");
        })}>
          <Field label="Message to companion" hint="Uses a permitted provider from Connectors and may consume your configured quota."><textarea required maxLength={50000} rows={3} value={message} onChange={(e) => setMessage(e.target.value)} /></Field><Button type="submit" disabled={!profile.enabled} busy={busy === "message"}>Run companion with selected procedures</Button>
        </form>{answer && <pre className="agent-team-result" aria-label="Companion result">{answer}</pre>}
      </Panel>}
      {owner && <Panel title="Five role actions">
        <p>Scout observes. Maker queues a timeline for review. Poster creates drafts. Analyst reads metrics. Director drafts a plan. Approval and publication stay in their existing review screens.</p>
        <form className="form-stack" onSubmit={(e) => submit(e, "role", async () => {
          const payload = { role, ...(role !== "Scout" && role !== "Director" ? { campaign_id: campaign } : {}), ...(role === "Maker" ? { topic } : {}), ...(role === "Poster" ? { image_campaign_id: imageCampaign, account_ids: accountIds } : {}), ...(role === "Director" ? { gtm_request: { product_id: product, goal_kind: "replies", goal_target: target, horizon_days: days, contact_budget: 0, channels: [], assumed_reply_rate: 0.034, per_identity_daily_cap: 30, notes: "", use_model: true } } : {}) };
          setRoleResult(await api.post<RoleOutcome>("/agent-team/execute", payload, idempotencyKey("role"))); setResultCampaign(campaign);
        })}>
          <Field label="Role"><select aria-label="Role" value={role} onChange={(e) => { setRole(e.target.value as Role); setRoleResult(null); }}>{ROLES.map((name) => <option key={name}>{name}</option>)}</select></Field>
          {!enabledProfiles.some((p) => p.name.toLowerCase() === role.toLowerCase()) && <p className="form-note">Set up the five roles and enable the selected companion first.</p>}
          {role !== "Scout" && role !== "Director" && <Field label="Role campaign"><select aria-label="Role campaign" required value={campaign} onChange={(e) => setCampaign(e.target.value)}><option value="">Choose a campaign</option>{roleCampaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>}
          {role !== "Scout" && role !== "Director" && !roleCampaigns.length && <p className="form-note"><a href="#campaigns">Create {role === "Maker" ? "an image" : "a distribution"} campaign</a> to use this role.</p>}
          {role === "Maker" && <Field label="Video topic"><input required maxLength={500} value={topic} onChange={(e) => setTopic(e.target.value)} /></Field>}
          {role === "Poster" && <><Field label="Image campaign"><select aria-label="Image campaign" required value={imageCampaign} onChange={(e) => setImageCampaign(e.target.value)}><option value="">Choose approved imagery</option>{campaigns.filter((c) => c.kind === "image").map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><Loadable loading={accounts.loading} error={accounts.error} />{accounts.error && <Button type="button" onClick={accounts.reload}>Retry posting accounts</Button>}{(accounts.data?.items ?? []).filter((a) => a.enabled).map((a) => <label className="checkbox-row" key={a.id}><input type="checkbox" checked={accountIds.includes(a.id)} onChange={() => setAccountIds(toggle(accountIds, a.id))} />{a.label || a.handle}</label>)}{!accounts.data?.items.length && <a href="#posting">Connect a posting account</a>}</>}
          {role === "Director" && <><Loadable loading={products.loading} error={products.error} />{products.error && <Button type="button" onClick={products.reload}>Retry products</Button>}<Field label="Strategy product"><select aria-label="Strategy product" required value={product} onChange={(e) => setProduct(e.target.value)}><option value="">Choose a product</option>{products.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>{!products.data?.items.length && <a href="#product">Create a product</a>}<Field label="Reply target"><input type="number" min={1} max={1000000} required value={target} onChange={(e) => setTarget(e.target.valueAsNumber)} /></Field><Field label="Horizon days"><input type="number" min={1} max={365} required value={days} onChange={(e) => setDays(e.target.valueAsNumber)} /></Field></>}
          {role !== "Scout" && <p className="form-note">Generating media or a plan may consume configured provider quota.</p>}
          <Button type="submit" busy={busy === "role"} disabled={!enabledProfiles.some((p) => p.name.toLowerCase() === role.toLowerCase()) || (role === "Poster" && !accountIds.length)}>Run selected role</Button>
        </form>{roleResult !== null && <RoleResultView value={roleResult} open={(page) => { if (resultCampaign) selectCampaign(resultCampaign); window.location.hash = page; }} />}
      </Panel>}
      {owner && profile && <Panel title="Bounded child reasoning">
        <p>Select one to three different companions. Children return brief findings; the parent sees their results, not private transcripts. This can use up to four provider calls. Children cannot run tools or create grandchildren. Child reasoning uses profile instructions only; procedures and saved memory are not included.</p>
        <form className="form-stack" onSubmit={(e) => submit(e, "delegate", async () => {
          const ids = assignments.map((a) => a.companion_id);
          if (ids.includes(selected) || new Set(ids).size !== ids.length) throw new Error("Choose different children; the parent cannot select itself.");
          setDelegated(await api.post<DelegationOutcome>(`/companions/${profile.id}/delegate`, { assignments }, idempotencyKey("delegate")));
        })}>
          {assignments.map((assignment, index) => <fieldset key={index}><legend>Child {index + 1}</legend><Field label={`Child ${index + 1} companion`}><select aria-label={`Child ${index + 1} companion`} required value={assignment.companion_id} onChange={(e) => setAssignments(assignments.map((a, i) => i === index ? { ...a, companion_id: e.target.value } : a))}><option value="">Choose a child</option>{enabledProfiles.filter((p) => p.id !== selected).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field><Field label={`Child ${index + 1} goal`}><textarea required maxLength={2000} rows={2} value={assignment.goal} onChange={(e) => setAssignments(assignments.map((a, i) => i === index ? { ...a, goal: e.target.value } : a))} /></Field>{assignments.length > 1 && <Button type="button" tone="secondary" onClick={() => setAssignments(assignments.filter((_, i) => i !== index))}>Remove child {index + 1}</Button>}</fieldset>)}
          <div className="page-actions"><Button type="button" tone="secondary" disabled={assignments.length >= 3} onClick={() => setAssignments([...assignments, { companion_id: "", goal: "" }])}>Add child</Button><Button type="submit" disabled={!profile.enabled} busy={busy === "delegate"}>Run bounded reasoning</Button></div>
        </form>{delegated !== null && <DelegationResultView value={delegated} />}
      </Panel>}
    </fieldset>
    {confirm && <Modal open title={`Delete ${confirm.name}?`} description={confirm.kind === "profile" ? "This removes the profile. Existing approved memory remains in the workspace until separately deleted." : "This procedure will be unavailable to future runs."} onClose={() => { if (!busy) setConfirm(null); }}><Button tone="danger" busy={busy === "delete"} onClick={() => void removeConfirmed()}>Confirm deletion</Button><Button tone="secondary" disabled={Boolean(busy)} onClick={() => setConfirm(null)}>Cancel</Button></Modal>}
  </>;
}
