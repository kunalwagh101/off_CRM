import { useEffect, useId, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export function Button({
  tone = "primary",
  busy = false,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "secondary" | "danger" | "ghost";
  busy?: boolean;
}) {
  return (
    <button className={`button button-${tone}`} disabled={disabled || busy} {...props}>
      {busy ? <span className="spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function StatCard({
  label,
  value,
  detail,
  accent = "blue"
}: {
  label: string;
  value: string | number;
  detail?: string;
  accent?: "blue" | "green" | "orange" | "violet";
}) {
  return (
    <article className={`stat-card stat-${accent}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      {detail ? <span>{detail}</span> : null}
    </article>
  );
}

export function StatePanel({
  title,
  description,
  action,
  tone = "empty"
}: {
  title: string;
  description: string;
  action?: ReactNode;
  tone?: "empty" | "error" | "loading";
}) {
  return (
    <div className={`state-panel state-${tone}`} role={tone === "error" ? "alert" : undefined}>
      {tone === "loading" ? <span className="spinner spinner-large" aria-hidden="true" /> : null}
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = ""
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title || action ? (
        <div className="panel-header">
          <div>
            {title ? <h2>{title}</h2> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  wide = false
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();

    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((item) => !item.hasAttribute("hidden") && item.getAttribute("aria-hidden") !== "true");
      if (!focusable.length) {
        event.preventDefault();
        closeRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      const target = returnFocusRef.current;
      window.requestAnimationFrame(() => target?.focus());
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        ref={dialogRef}
        className={`modal ${wide ? "modal-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p id={descriptionId}>{description}</p> : null}
          </div>
          <button ref={closeRef} className="icon-button" onClick={onClose} aria-label="Close dialog">
            ×
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

export function Field({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

export function Progress({ value }: { value: number }) {
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label={`Quality score ${bounded} out of 100`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={bounded}
    >
      <span style={{ width: `${bounded}%` }} />
    </div>
  );
}
