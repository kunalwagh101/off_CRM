import { useMemo, useState } from "react";
import { api } from "../api";
import { Badge, Button } from "../components";
import { useApp } from "../context";
import type { AIProviderRow, DiscoveredModel, DiscoveryResult } from "../types";

const TIER_TONE: Record<string, string> = { A: "success", B: "neutral", C: "warning", D: "danger" };
const TIER_WORD: Record<string, string> = {
  A: "Highest trust",
  B: "Default trust",
  C: "Restricted",
  D: "Blocked"
};

/** Family label from a model id, so a long list reads as groups. */
function familyOf(modelId: string): string {
  const prefix = modelId.includes("/") ? modelId.split("/")[0] : "other";
  return (
    {
      "meta": "Meta (Llama)",
      "meta-llama": "Meta (Llama)",
      "deepseek-ai": "DeepSeek",
      "qwen": "Qwen (Alibaba)",
      "moonshotai": "Moonshot (Kimi)",
      "microsoft": "Microsoft (Phi)",
      "mistralai": "Mistral",
      "google": "Google (Gemma)",
      "nvidia": "NVIDIA (Nemotron)",
      "ibm": "IBM (Granite)",
      "zhipuai": "Zhipu (GLM)"
    }[prefix] ?? prefix
  );
}

/**
 * Choose which models a key should use.
 *
 * One NVIDIA key reaches 100+ models built by different companies, and a model
 * carries its own trust tier — DeepSeek on NVIDIA is still restricted. So this
 * list shows a tier badge per model, not per provider, and a model whose origin
 * off_CRM cannot place is disabled with the reason on it rather than hidden.
 */
export default function ModelPicker({
  provider,
  onSaved
}: {
  provider: AIProviderRow;
  onSaved: () => void;
}) {
  const { notify } = useApp();
  const [selected, setSelected] = useState<string[]>(
    provider.model_ids?.length ? provider.model_ids : [provider.model_id]
  );
  const [discovered, setDiscovered] = useState<DiscoveryResult | null>(null);
  const [busy, setBusy] = useState("");
  const [filter, setFilter] = useState("");

  // Config models until the owner asks the provider for the live list.
  const models: DiscoveredModel[] = useMemo(() => {
    if (discovered) return discovered.models;
    return (provider.available_models ?? []).map((model) => ({
      id: model.id,
      origin: model.model_origin,
      tier: model.tier,
      tier_cap: model.model_origin_tier_cap,
      known: true,
      in_config: true,
      matched_prefix: "",
      usable: model.tier !== "D",
      policy_ceiling: ""
    }));
  }, [discovered, provider.available_models]);

  // Only models off_CRM can place a trust level on may be turned on.
  const usable = useMemo(() => models.filter((model) => model.usable), [models]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const matching = needle ? models.filter((m) => m.id.toLowerCase().includes(needle)) : models;
    const groups = new Map<string, DiscoveredModel[]>();
    for (const model of matching) {
      const family = familyOf(model.id);
      groups.set(family, [...(groups.get(family) ?? []), model]);
    }
    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [models, filter]);

  function toggle(model: DiscoveredModel) {
    if (!model.usable) return;
    setSelected((prev) =>
      prev.includes(model.id) ? prev.filter((id) => id !== model.id) : [...prev, model.id]
    );
  }

  async function findModels() {
    setBusy("discover");
    try {
      const result = await api.post<DiscoveryResult>(
        `/ai/providers/${provider.id}/discover-models`,
        {}
      );
      setDiscovered(result);
      if (result.error) notify(result.error, "warning");
      else notify(`${provider.name} reports ${result.total} models · ${result.usable} usable`, "success");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not fetch the model list", "error");
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (selected.length === 0) {
      notify("Pick at least one model.", "warning");
      return;
    }
    setBusy("save");
    try {
      await api.post(`/ai/providers/${provider.id}/connect`, {
        model_ids: selected,
        data_policy: provider.data_policy
      });
      notify(
        `${provider.name}: ${selected.length} model${selected.length === 1 ? "" : "s"} enabled`,
        "success"
      );
      onSaved();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not save", "error");
    } finally {
      setBusy("");
    }
  }

  const tiersInSelection = new Set(
    models.filter((m) => selected.includes(m.id)).map((m) => m.tier)
  );

  return (
    <section className="model-picker">
      <header className="model-picker-head">
        <div>
          <strong>Models on this key</strong>
          <small>
            {selected.length} of {usable.length} usable enabled
            {discovered ? ` · live list from ${provider.name}` : " · from config"}
          </small>
        </div>
        {provider.supports_model_discovery ? (
          <Button tone="ghost" busy={busy === "discover"} onClick={findModels}>
            Find models
          </Button>
        ) : null}
      </header>

      {/* One key can run every model on it. Turning them all on is a normal
          thing to want, so it should not need N clicks. */}
      <div className="model-bulk">
        <button
          type="button"
          className="link-button"
          onClick={() => setSelected(usable.map((model) => model.id))}
          disabled={selected.length === usable.length}
        >
          Select all {usable.length}
        </button>
        <button
          type="button"
          className="link-button"
          onClick={() => setSelected([])}
          disabled={selected.length === 0}
        >
          Clear
        </button>
        {visible.length > 0 && filter.trim() ? (
          <button
            type="button"
            className="link-button"
            onClick={() =>
              setSelected((prev) => [
                ...new Set([
                  ...prev,
                  ...visible.flatMap(([, group]) => group.filter((m) => m.usable).map((m) => m.id))
                ])
              ])
            }
          >
            Select the {visible.reduce((n, [, g]) => n + g.filter((m) => m.usable).length, 0)} shown
          </button>
        ) : null}
      </div>

      {tiersInSelection.size > 1 ? (
        <p className="model-picker-note">
          You have picked models at different trust levels. Each one only receives what its own
          level allows, so they will not all see the same detail.
        </p>
      ) : null}

      {discovered?.note ? <p className="model-picker-note">{discovered.note}</p> : null}

      {models.length > 8 ? (
        <input
          className="model-filter"
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder={`Search ${models.length} models…`}
          aria-label="Filter models"
        />
      ) : null}

      <div className="model-groups">
        {visible.map(([family, group]) => {
          const groupUsable = group.filter((model) => model.usable);
          const allOn =
            groupUsable.length > 0 && groupUsable.every((model) => selected.includes(model.id));
          return (
          <div key={family} className="model-group">
            {/* One key hosts several makers, and wanting "every Microsoft model"
                or "every DeepSeek model" is normal. The header toggles the whole
                maker at once — still only the usable ones. */}
            <div className="model-group-head">
              <p className="model-group-label">
                {family}
                <span className="model-group-count">
                  {groupUsable.filter((m) => selected.includes(m.id)).length}/{groupUsable.length}
                </span>
              </p>
              {groupUsable.length > 1 ? (
                <button
                  type="button"
                  className="link-button"
                  onClick={() =>
                    setSelected((prev) =>
                      allOn
                        ? prev.filter((id) => !groupUsable.some((m) => m.id === id))
                        : [...new Set([...prev, ...groupUsable.map((m) => m.id)])]
                    )
                  }
                >
                  {allOn ? `Remove all ${family}` : `Add all ${groupUsable.length}`}
                </button>
              ) : null}
            </div>
            {group.map((model) => {
              const on = selected.includes(model.id);
              return (
                <label
                  key={model.id}
                  className={
                    !model.usable
                      ? "model-option model-option-blocked"
                      : on
                      ? "model-option model-option-on"
                      : "model-option"
                  }
                >
                  <input
                    type="checkbox"
                    checked={on}
                    disabled={!model.usable}
                    onChange={() => toggle(model)}
                  />
                  <span className="model-option-id">{model.id}</span>
                  <Badge tone={TIER_TONE[model.tier] ?? "neutral"}>
                    {TIER_WORD[model.tier] ?? model.tier}
                  </Badge>
                  {!model.known ? (
                    <small className="model-option-why">
                      off_CRM cannot tell who built this. Add a rule in
                      config/providers.yaml to use it.
                    </small>
                  ) : model.tier_cap ? (
                    <small className="model-option-why">
                      Built in {model.origin} — restricted wherever it is hosted.
                    </small>
                  ) : null}
                </label>
              );
            })}
          </div>
          );
        })}
      </div>

      {visible.length === 0 ? (
        <p className="muted-copy">No model matches “{filter}”.</p>
      ) : null}

      <div className="button-row">
        <Button busy={busy === "save"} onClick={save} disabled={selected.length === 0}>
          Save {selected.length} model{selected.length === 1 ? "" : "s"}
        </Button>
      </div>
    </section>
  );
}
