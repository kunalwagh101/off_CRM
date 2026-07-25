import { createContext, useContext } from "react";
import type { Campaign } from "./types";

export type AppContextValue = {
  campaigns: Campaign[];
  campaignId: string;
  activeCampaign: Campaign | null;
  selectCampaign: (id: string) => void;
  refreshCampaigns: () => void;
  notify: (message: string, tone?: "success" | "error" | "info" | "warning") => void;
};

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("AppContext is missing");
  return value;
}
