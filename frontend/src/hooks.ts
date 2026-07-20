import { useCallback, useEffect, useState, type DependencyList } from "react";

export type Resource<T> = {
  data: T | null;
  loading: boolean;
  error: string;
  reload: () => void;
};

export function useResource<T>(loader: () => Promise<T>, dependencies: DependencyList): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    loader()
      .then((value) => {
        if (active) setData(value);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Request failed");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // The caller owns the dependency list, with revision added for reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, revision]);

  return { data, loading, error, reload };
}

export function formatDate(value?: string): string {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short"
      }).format(date);
}

export function stageLabel(value?: string): string {
  return (
    {
      initial: "First touch",
      followup1: "Follow-up 1",
      followup2: "Follow-up 2"
    }[value ?? ""] ?? value ?? "Not started"
  );
}
