import { CircleAlert, Info, TriangleAlert } from "lucide-react";

// The few shared pieces the page draws by hand, styled in app.css.

export function Spinner({ label }) {
  return (
    <span className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </span>
  );
}

const NOTICE_ICONS = { info: Info, warning: TriangleAlert, error: CircleAlert };

export function Notice({ kind = "info", title, children, role }) {
  const Icon = NOTICE_ICONS[kind];
  return (
    <div
      className={`notice notice--${kind}`}
      role={role ?? (kind === "error" ? "alert" : "status")}
    >
      <Icon size={18} aria-hidden="true" />
      <div>
        {title ? <strong>{title}</strong> : null}
        {children}
      </div>
    </div>
  );
}
