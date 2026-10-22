import { useEffect, useId, useRef, useState } from "react";
import { errorText } from "./adminData";

export function PageHeading({ title, description, onCreate, createLabel = "Thêm mới" }) {
  return <div className="admin-heading"><div><p className="admin-eyebrow">Điều hành rạp chiếu</p><h1>{title}</h1><p>{description}</p></div>
    {onCreate && <button className="admin-primary" onClick={onCreate}>＋ {createLabel}</button>}</div>;
}

export function Field({ label, children, ...props }) {
  const id = useId();
  return <div className="admin-field"><label htmlFor={id}>{label}</label>
    {children ? <select id={id} {...props}>{children}</select> : props.type === "textarea"
      ? <textarea id={id} {...props} type={undefined} rows={6} /> : <input id={id} {...props} />}</div>;
}

export function MultiChoice({ label, items, value, onChange }) {
  return <fieldset className="admin-choices"><legend>{label}</legend>{items.map((item) =>
    <label key={item.id}><input type="checkbox" checked={value.includes(item.id)} onChange={(e) =>
      onChange(e.target.checked ? [...value, item.id] : value.filter((id) => id !== item.id))} />{item.name}</label>)}</fieldset>;
}

export function Dialog({ title, children, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className="admin-dialog" aria-label={title} onCancel={(event) => {
    event.preventDefault(); onClose();
  }}><header><h2>{title}</h2><button type="button" aria-label="Đóng" onClick={onClose}>×</button></header>{children}</dialog>;
}

export function Editor({ title, initial, onSave, onClose, children, submitLabel = "Lưu thay đổi" }) {
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key) => (event) => setValue((old) => ({ ...old, [key]: event.target.value }));
  return <Dialog title={title} onClose={() => { if (!busy) onClose(); }}>
    <form onSubmit={async (event) => {
      event.preventDefault(); setBusy(true); setError("");
      try { await onSave(value); onClose(); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
    }}><fieldset disabled={busy} className="admin-form-fields">{children(value, set, setValue)}</fieldset>
      {error && <p className="admin-error" role="alert">{error}</p>}
      <footer><button type="button" disabled={busy} onClick={onClose}>Hủy</button>
        <button className="admin-primary" disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button></footer>
    </form>
  </Dialog>;
}

export function ConfirmAction({ title, description, onConfirm, onClose }) {
  return <Editor title={title} initial={{}} onSave={onConfirm} onClose={onClose} submitLabel="Xác nhận">
    {() => <p>{description}</p>}</Editor>;
}

export function DataTable({ columns, rows = [], loading, error, reload, actions }) {
  if (loading) return <p className="admin-empty" role="status">Đang tải dữ liệu…</p>;
  if (error) return <div className="admin-empty"><p role="alert" className="admin-error">{error}</p><button onClick={reload}>Thử lại</button></div>;
  return <div className="admin-table-scroll"><table className="admin-table"><thead><tr>{columns.map((column) =>
    <th key={column.key} scope="col">{column.label}</th>)}{actions && <th scope="col">Thao tác</th>}</tr></thead>
    <tbody>{rows.length ? rows.map((row) => <tr key={row.id}>{columns.map((column) =>
      <td key={column.key}>{column.render ? column.render(row) : row[column.key] ?? "—"}</td>)}
      {actions && <td><div className="admin-row-actions">{actions(row)}</div></td>}</tr>)
      : <tr><td colSpan={columns.length + (actions ? 1 : 0)} className="admin-empty">Chưa có dữ liệu phù hợp.</td></tr>}</tbody></table></div>;
}

export function Pagination({ total = 0, offset, onChange, limit = 20 }) {
  return <div className="admin-pagination"><span>{total ? `${offset + 1}–${Math.min(offset + limit, total)} / ${total} bản ghi` : "0 bản ghi"}</span>
    <div><button disabled={!offset} onClick={() => onChange(Math.max(0, offset - limit))}>Trước</button>
      <button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Sau</button></div></div>;
}
