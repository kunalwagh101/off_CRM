// Provider profiles saved before off_CRM recorded whose each one is (DD-68).
// They are in no draft chain until the install owner settles them, and no
// other screen lists profiles (D-173), so this is where that happens (D-177).
import { Button } from "../components";
import type { ProviderProfile } from "../types";

type Row = Pick<ProviderProfile, "id" | "owner" | "name" | "provider_type" | "model" | "base_url" | "owner_confirmed">;

/** What the Drafts screen says under its model option. It pointed at a
 * Settings form that no longer exists (D-173), and could not say that the
 * owner's old profiles were waiting (D-177). */
export function draftsProfileNote(total: number, waiting: number): string {
  if (total > 0) return "";
  if (waiting === 1) {
    return "1 saved provider profile is waiting for you to confirm it in Settings, under Provider profiles to confirm.";
  }
  if (waiting > 1) {
    return `${waiting} saved provider profiles are waiting for you to confirm them in Settings, under Provider profiles to confirm.`;
  }
  return "Personalising with a model needs a provider profile, and no screen adds one yet. Drafts use local templates until then.";
}

/** Confirming gives a profile to the workspace its old label names — you, for
 * "default" — never anywhere else. So each row shows where it sends and who it
 * was saved for: a label anyone could have typed is not proof it is yours. */
export default function LegacyProfiles({
  items,
  busy,
  onConfirm,
  onRemove
}: {
  items: Row[];
  busy: string;
  onConfirm: (profile: Row) => void;
  onRemove: (profile: Row) => void;
}) {
  const waiting = items.filter((item) => !item.owner_confirmed);
  if (!waiting.length) return null;
  return (
    <ul className="legacy-profiles">
      {waiting.map((item) => (
        <li key={item.id}>
          <div className="legacy-profile-facts">
            <strong>{item.name}</strong>
            <small>
              {item.provider_type} · {item.model || "its default model"}
            </small>
            <small>Sends to: {item.base_url || "the provider's own address"}</small>
            <small>Saved for: {item.owner || "no one"}</small>
          </div>
          <div className="button-row">
            <Button
              tone="ghost"
              aria-label={`Confirm ${item.name}`}
              busy={busy === `provider-confirm-${item.id}`}
              onClick={() => onConfirm(item)}
            >
              Confirm
            </Button>
            <Button
              tone="ghost"
              aria-label={`Remove ${item.name}`}
              busy={busy === `provider-delete-${item.id}`}
              onClick={() => onRemove(item)}
            >
              Remove
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
