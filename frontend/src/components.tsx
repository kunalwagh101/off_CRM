import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode
} from "react";

const DIALOG_FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

function dialogFocusable(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(DIALOG_FOCUSABLE)).filter(
    (element) => element.getAttribute("aria-hidden") !== "true"
  );
}

export function dialogTabTarget(
  currentIndex: number,
  total: number,
  backwards: boolean
): number | null {
  if (total <= 0) return 0;
  if (currentIndex < 0) return backwards ? total - 1 : 0;
  if (backwards && currentIndex === 0) return total - 1;
  if (!backwards && currentIndex === total - 1) return 0;
  return null;
}

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
    <button
      className={`button button-${tone}`}
      disabled={disabled || busy}
      {...props}
      aria-busy={busy || undefined}
    >
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
  const role = tone === "error" ? "alert" : tone === "loading" ? "status" : undefined;
  return (
    <div
      className={`state-panel state-${tone}`}
      role={role}
      aria-live={tone === "loading" ? "polite" : undefined}
      aria-atomic={tone === "loading" ? "true" : undefined}
    >
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
    returnFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const frame = window.requestAnimationFrame(() => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      const explicit = dialog.querySelector<HTMLElement>("[autofocus]");
      (explicit ?? closeRef.current ?? dialog).focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
      returnFocusRef.current?.focus();
      returnFocusRef.current = null;
    };
  }, [open]);

  function handleKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = dialogFocusable(dialog);
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const current = document.activeElement instanceof HTMLElement
      ? focusable.indexOf(document.activeElement)
      : -1;
    const target = dialogTabTarget(current, focusable.length, event.shiftKey);
    if (target === null) return;
    event.preventDefault();
    focusable[target]?.focus();
  }

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
        tabIndex={-1}
        onKeyDown={handleKeyDown}
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
  const normalised = Math.max(0, Math.min(100, value));
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label="Quality score"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={normalised}
      aria-valuetext={`${normalised} out of 100`}
    >
      <span style={{ width: `${normalised}%` }} />
    </div>
  );
}
