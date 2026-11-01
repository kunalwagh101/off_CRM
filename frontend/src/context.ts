import { createContext, useContext } from "react";
import type { Campaign } from "./types";

export type AppContextValue = {
  publicDemo?: boolean;
  campaigns: Campaign[];
  campaignId: string;
  activeCampaign: Campaign | null;
  selectCampaign: (id: string) => void;
  /** Create a campaign and select it; the selection survives the list refresh (S-06.02.22). */
  createCampaign: (body: Record<string, unknown>) => Promise<Campaign>;
  refreshCampaigns: () => void;
  notify: (message: string, tone?: "success" | "error" | "info" | "warning") => void;
};

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("AppContext is missing");
  return value;
}
