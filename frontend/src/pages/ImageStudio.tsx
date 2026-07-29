import { useState } from "react";
import { api } from "../api";
import { Badge, Button, StatePanel } from "../components";
import { useApp } from "../context";
import type { AIProviderRow } from "../types";
import { ModelStrip } from "./AIStudio";

const TIER_TONE: Record<string, string> = { A: "success", B: "neutral", C: "warning", D: "danger" };

type ImageRun = {
  images: string[];
  prompt: string;
  provider_id: string;
  provider_name: string;
  model_id: string;
  tier: string;
  policy: string;
  duration_ms: number;
  log_id: string;
};

/**
 * Draw pictures from a prompt.
 *
 * The same key that runs your text models also runs image models — NVIDIA hosts
 * FLUX and Stable Diffusion alongside Llama. The trust rules do not change here:
 * the prompt is still text, so a prompt naming a real person is still person
 * data and only trusted models will take it.
 */
export default function ImageStudio({ providers }: { providers: AIProviderRow[] }) {
  const { notify } = useApp();
  const [prompt, setPrompt] = useState("");
  const [modelChoice, setModelChoice] = useState("");
  const [aboutPerson, setAboutPerson] = useState(false);
  const [running, setRunning] = useState(false);
  const [runs, setRuns] = useState<ImageRun[]>([]);

  // Only models marked as image models can answer here.
  const imageChoices = providers
    .filter((row) => row.connected && row.enabled)
    .flatMap((row) => {
      const enabled = row.model_ids?.length ? row.model_ids : [row.model_id];
      return (row.available_models ?? [])
        .filter((model) => model.is_image && enabled.includes(model.id))
        .map((model) => ({
          key: `${row.id}:${model.id}`,
          label: `${row.flag} ${row.name} · ${model.id}`,
          tier: model.tier
        }));
    });

  async function draw() {
    if (!prompt.trim()) return;
    setRunning(true);
    try {
      const [providerId, ...rest] = modelChoice.split(":");
      const run = await api.post<ImageRun>("/ai/image", {
        prompt: prompt.trim(),
        data_class: aboutPerson ? "person_public" : "public",
        provider_id: modelChoice ? providerId : "",
        model_id: modelChoice ? rest.join(":") : ""
      });
      setRuns((prev) => [run, ...prev]);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not make the picture", "error");
    } finally {
      setRunning(false);
    }
  }

  function download(image: string, index: number) {
    const link = document.createElement("a");
    link.href = image;
    link.download = `off-crm-image-${index + 1}.png`;
    link.click();
  }

  return (
    <div className="studio">
      <ModelStrip providers={providers} compact />

      {imageChoices.length === 0 ? (
        <StatePanel
          title="No image model switched on"
          description="Image models live on the same key as your text models. Open Connectors, press Models on NVIDIA, and tick FLUX or Stable Diffusion."
          action={<Button onClick={() => (window.location.hash = "connectors")}>Open Connectors</Button>}
        />
      ) : null}

      <div className="studio-composer">
        <label className="studio-field">
          <span>Describe the picture</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={3}
            placeholder="A clean flat illustration of a cargo ship at a European port, muted blues, no text"
            disabled={running}
          />
        </label>

        <div className="studio-controls">
          <label className="ai-control">
            <span>Model</span>
            <select value={modelChoice} onChange={(event) => setModelChoice(event.target.value)}>
              <option value="">
                {imageChoices.length ? "Best available" : "No image model available"}
              </option>
              {imageChoices.map((choice) => (
                <option key={choice.key} value={choice.key}>
                  {choice.label} · {choice.tier}
                </option>
              ))}
            </select>
          </label>

          <label className="ai-control ai-control-check">
            <input
              type="checkbox"
              checked={aboutPerson}
              onChange={(event) => setAboutPerson(event.target.checked)}
            />
            <span>This picture is about a real person</span>
          </label>

          <p className="ai-control-note">
            {aboutPerson
              ? "Treated as personal information, so only trusted models will take it."
              : "Treated as a general prompt. Do not name a real person unless you tick the box."}
          </p>

          <Button onClick={draw} busy={running} disabled={!prompt.trim() || imageChoices.length === 0}>
            Make picture
          </Button>
        </div>
      </div>

      {running ? (
        <div className="image-grid">
          <div className="image-card image-card-loading" aria-hidden="true">
            <div className="image-skeleton" />
            <p className="muted-copy">Drawing… this usually takes 5–20 seconds.</p>
          </div>
        </div>
      ) : null}

      {runs.map((run, runIndex) => (
        <section key={`${run.log_id}-${runIndex}`} className="image-run">
          <p className="studio-summary">
            <strong>{run.provider_name}</strong> · {run.model_id} ·{" "}
            <Badge tone={TIER_TONE[run.tier] ?? "neutral"}>{run.tier}</Badge> ·{" "}
            {(run.duration_ms / 1000).toFixed(1)}s
          </p>
          <p className="image-prompt">{run.prompt}</p>
          <div className="image-grid">
            {run.images.map((image, index) => (
              <figure key={index} className="image-card">
                <img src={image} alt={run.prompt} loading="lazy" />
                <figcaption>
                  <Button tone="ghost" onClick={() => download(image, index)}>
                    Download
                  </Button>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      ))}

      {runs.length === 0 && !running && imageChoices.length > 0 ? (
        <StatePanel
          title="Make a picture"
          description="Uses the same key as your text models. Pictures come back as files you can download and use in an email or anywhere else."
        />
      ) : null}
    </div>
  );
}
