import { useId } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Film, Loader2 } from "lucide-react";

export function Button({
  to,
  variant = "primary",
  busy = false,
  children,
  className = "",
  disabled,
  ...props
}) {
  const classes = `btn btn-${variant} ${className}`;
  if (to)
    return (
      <Link to={to} className={classes} {...props}>
        {children}
      </Link>
    );
  return (
    <button
      type="button"
      className={classes}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...props}
    >
      {busy && (
        <Loader2 size={18} className="animate-spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
export function FormField({
  label,
  hint,
  error,
  id: givenId,
  children,
  className = "",
  ...props
}) {
  const generatedId = useId();
  const id = givenId || generatedId;
  return (
    <div className={`form-field ${className}`}>
      <label htmlFor={id}>{label}</label>
      {children || (
        <input
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={error || hint ? `${id}-hint` : undefined}
          {...props}
        />
      )}
      {(error || hint) && (
        <p
          id={`${id}-hint`}
          className={error ? "text-red-700 text-sm" : "text-gray-500 text-sm"}
        >
          {error || hint}
        </p>
      )}
    </div>
  );
}
export function PageState({
  loading = false,
  title,
  message,
  onRetry,
  children,
}) {
  return (
    <div
      className="page-state"
      role={loading ? "status" : onRetry ? "alert" : "status"}
    >
      {loading ? (
        <Loader2
          className="animate-spin text-red-600"
          size={32}
          aria-hidden="true"
        />
      ) : onRetry ? (
        <AlertCircle className="text-red-600" size={32} aria-hidden="true" />
      ) : (
        <Film className="text-gray-400" size={32} aria-hidden="true" />
      )}
      <h2>{title || (loading ? "Đang tải…" : "Chưa có dữ liệu")}</h2>
      {message && <p>{message}</p>}
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Thử lại
        </Button>
      )}
      {children}
    </div>
  );
}
export function Poster({ src, title, className = "", ...props }) {
  return (
    <img
      src={src || "/poster-placeholder.svg"}
      alt={title || "Poster phim"}
      className={`poster ${className}`}
      onError={(e) => {
        e.currentTarget.onerror = null;
        e.currentTarget.src = "/poster-placeholder.svg";
      }}
      {...props}
    />
  );
}
export function BookingSteps({ current = 0 }) {
  return (
    <ol className="booking-steps" aria-label="Tiến trình đặt vé">
      {["Lịch chiếu", "Chọn ghế", "Thanh toán", "Nhận vé"].map(
        (label, index) => (
          <li
            key={label}
            aria-current={current === index ? "step" : undefined}
            className={
              index === current
                ? "is-current"
                : index < current
                  ? "is-done"
                  : ""
            }
          >
            <span>{index + 1}</span>
            <strong>{label}</strong>
          </li>
        ),
      )}
    </ol>
  );
}
