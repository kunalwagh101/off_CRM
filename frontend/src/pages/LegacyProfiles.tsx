// Provider profiles saved before off_CRM recorded whose each one is (DD-68).
// They are in no draft chain until the install owner settles them, and no
// other screen lists profiles (D-173), so this is where that happens (D-177).
import { Button } from "../components";
import type { ProviderProfile } from "../types";

type Row = Pick<
  ProviderProfile,
  "id" | "owner" | "name" | "provider_type" | "model" | "base_url" | "has_stored_secret" | "owner_confirmed"
> & { confirm_to?: string; confirm_options?: string[] };

/** What the Drafts screen says under its model option. It pointed at a
 * Settings form that no longer exists (D-173), and could not say that the
 * owner's old profiles were waiting (D-177). */
export function draftsProfileNote(total: number, waiting: number): string {
  if (total > 0) return "";
  if (waiting === 1) {
    return "1 saved provider profile is waiting for you in Settings, under Provider profiles to confirm.";
  }
  if (waiting > 1) {
    return `${waiting} saved provider profiles are waiting for you in Settings, under Provider profiles to confirm.`;
  }
  return "Personalising with a model needs a provider profile, and no screen adds one yet. Drafts use local templates until then.";
}

/** Where Enter in the key box confirms a profile: the one place it can go,
 * or nowhere when there is a choice. Enter presses no button of its own, and
 * letting the first one choose sent the owner's key to a client (D-197). */
export function enterDestination(destinations: string[]): string {
  return destinations.length === 1 ? destinations[0] : "";
}

const typedKey = (form: HTMLFormElement | null) =>
  (form?.elements.namedItem("api_key") as HTMLInputElement | null)?.value ?? "";

/** Confirming takes the key the profile holds: its label proves nothing —
 * every login's saves were once labelled "default" — and the key is what a
 * client's planted profile cannot give you (D-185). A profile labelled for a
 * client workspace goes back to it; any other is yours. */
export default function LegacyProfiles({
  items,
  busy,
  onConfirm,
  onRemove
}: {
  items: Row[];
  busy: string;
  onConfirm: (profile: Row, apiKey: string, destination: string) => void;
  onRemove: (profile: Row) => void;
}) {
  const waiting = items.filter((item) => !item.owner_confirmed);
  if (!waiting.length) return null;
  return (
    <ul className="legacy-profiles">
      {waiting.map((item) => {
        // One button per place it may go, each saying where, and heard by
        // screen readers too: a button's label replaces its text (D-190,
        // D-195). The one pressed is the one sent (D-194) — by its own
        // click, as not every browser reports a form's pressed button (D-197).
        const destinations = item.confirm_options ?? [item.confirm_to ?? "local"];
        const words = (destination: string) =>
          destination === "local" ? "as yours" : `for workspace ${destination}`;
        return (
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
            {item.has_stored_secret ? (
              <form
                className="legacy-profile-confirm"
                onSubmit={(event) => {
                  event.preventDefault();
                  onConfirm(item, typedKey(event.currentTarget), enterDestination(destinations));
                }}
              >
                <input
                  name="api_key"
                  type="password"
                  autoComplete="off"
                  placeholder="Its API key"
                  aria-label={`API key of ${item.name}`}
                />
                {destinations.map((destination) => (
                  <Button
                    key={destination}
                    type="button"
                    tone="ghost"
                    aria-label={`Confirm ${item.name} ${words(destination)}`}
                    busy={busy === `provider-confirm-${item.id}`}
                    onClick={(event) => onConfirm(item, typedKey(event.currentTarget.form), destination)}
                  >
                    Confirm {words(destination)}
                  </Button>
                ))}
              </form>
            ) : (
              // Without a key nothing proves whose it is; some types need none,
              // so "nothing can use it" was not always true (D-187, D-191).
              <small>No key is stored in it, so nothing proves it is yours. Remove it.</small>
            )}
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
        );
      })}
    </ul>
  );
}
