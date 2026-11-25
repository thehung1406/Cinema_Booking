import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../../config/api";
import { formatDate } from "../../utils/formatters";
import { ConfirmAction, DataTable, Field, PageHeading, Pagination } from "./AdminShared";
import { useAdminData } from "./adminData";

const sentiments = { positive: "Tích cực", neutral: "Trung lập", negative: "Tiêu cực" };
const analyses = { pending: "Chờ phân tích", failed: "Chưa phân tích được", succeeded: "Đã phân tích", needs_review: "Chờ phân tích lại" };
const visibility = { approved: "Công khai", rejected: "Không công khai", pending: "Chưa công khai" };

export default function ReviewsPage() {
  const [filters, setFilters] = useState({ q: "", film_id: "", sentiment: "", analysis_status: "", moderation_status: "" });
  const [offset, setOffset] = useState(0);
  const [deleting, setDeleting] = useState(null);
  const [notice, setNotice] = useState("");
  const list = useAdminData("/reviews", { ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "")), offset, limit: 20 });
  const filter = (key) => (event) => {
    setFilters(old => ({ ...old, [key]: event.target.value }));
    setOffset(0);
  };
  const columns = [
    { key: "author", label: "Người viết", render: row => <>{row.author}<small>Nhận xét #{row.id}{row.verified_purchase ? " · Đã mua vé" : ""}</small></> },
    { key: "film_id", label: "Phim", render: row => <Link to={`/movie/${row.film_id}`}>Phim #{row.film_id}</Link> },
    { key: "content", label: "Nội dung", render: row => row.content.length > 180
      ? <details className="admin-review-content"><summary>{row.content.slice(0, 180)}… <span>Xem đầy đủ</span></summary><p>{row.content}</p></details>
      : <p className="admin-review-content">{row.content}</p> },
    { key: "moderation_status", label: "Công khai", render: row => <span className={`admin-badge ${row.moderation_status === "approved" ? "success" : ""}`}>{visibility[row.moderation_status] || "Không xác định"}</span> },
    { key: "sentiment", label: "Cảm xúc", render: row => <>
      <span className={`admin-badge ${row.analysis_status !== "succeeded" ? "pending" : row.sentiment === "positive" ? "success" : row.sentiment === "negative" ? "negative" : ""}`}>
        {sentiments[row.sentiment] || analyses[row.analysis_status] || "Chưa phân tích"}
      </span>
      {row.sentiment && row.scores?.[row.sentiment] !== undefined && <small>Điểm mô hình: {(row.scores[row.sentiment] * 100).toFixed(1)}%</small>}
      {row.model_version && <small>{row.model_version}</small>}
    </> },
    { key: "updated_at", label: "Cập nhật", render: row => formatDate(row.updated_at) },
  ];
  return <>
    <PageHeading title="Nhận xét người dùng" description="Nhận xét mới được công khai ngay. Tra cứu cảm nhận của khán giả và xóa nội dung không phù hợp." />
    {notice && <p role="status" className="admin-notice">{notice}</p>}
    <section className="admin-panel" aria-label="Danh sách nhận xét">
      <div className="admin-toolbar">
        <Field label="Nội dung" type="search" placeholder="Tìm trong nhận xét…" maxLength={1000} value={filters.q} onChange={filter("q")} />
        <Field label="Mã phim" type="number" min="1" step="1" placeholder="Tất cả phim" value={filters.film_id} onChange={filter("film_id")} />
        <Field label="Cảm xúc" value={filters.sentiment} onChange={filter("sentiment")}><option value="">Tất cả cảm xúc</option>{Object.entries(sentiments).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Field>
        <Field label="Phân tích" value={filters.analysis_status} onChange={filter("analysis_status")}><option value="">Tất cả trạng thái</option>{Object.entries(analyses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Field>
        <Field label="Công khai" value={filters.moderation_status} onChange={filter("moderation_status")}><option value="">Tất cả nhận xét</option>{Object.entries(visibility).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Field>
      </div>
      <DataTable columns={columns} rows={list.data?.items} loading={list.loading} error={list.error} reload={list.reload}
        actions={row => <button className="admin-danger" onClick={() => { setNotice(""); setDeleting(row); }}>Xóa</button>} />
      <Pagination total={list.data?.total} offset={offset} onChange={setOffset} />
    </section>
    {deleting && <ConfirmAction title="Xóa nhận xét" description={`Xóa nhận xét #${deleting.id} của ${deleting.author}? Nội dung sẽ bị xóa và không thể khôi phục.`}
      onClose={() => setDeleting(null)} onConfirm={async () => {
        await api.delete(`/reviews/${deleting.id}`);
        setOffset(0); list.reload(); setNotice("Đã xóa nhận xét.");
      }} />}
  </>;
}
