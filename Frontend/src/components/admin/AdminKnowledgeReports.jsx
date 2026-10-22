import { useState } from "react";
import api from "../../config/api";
import { formatCurrency, formatDate, formatTime, localDateInput } from "../../utils/formatters";
import { ConfirmAction, DataTable, Dialog, Editor, Field, PageHeading, Pagination } from "./AdminShared";
import { errorText, useAdminData } from "./adminData";

function utcStamp(value) {
  return /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
}
function localDateTime(value = new Date().toISOString()) {
  const date = new Date(utcStamp(value));
  return `${localDateInput(date)}T${formatTime(date)}`;
}

function DocumentReview({ documentId, onClose, onEdit, onSaved }) {
  const detail = useAdminData(`/admin/documents/${documentId}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const doc = detail.data;
  const approve = async (approved) => {
    setBusy(true); setError("");
    try {
      await api.put(`/admin/documents/${documentId}/approval`, { approved, version: doc.version, expected_updated_at: utcStamp(doc.updated_at) });
      onSaved(approved ? "Đã phê duyệt tài liệu." : "Đã thu hồi phê duyệt tài liệu."); onClose();
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  return <Dialog title="Kiểm tra tài liệu tri thức" onClose={() => { if (!busy) onClose(); }}>
    <div className="admin-review">
      {detail.loading && <p role="status">Đang tải nội dung…</p>}
      {(detail.error || error) && <p className="admin-error" role="alert">{detail.error || error}</p>}
      {detail.error && <button onClick={detail.reload}>Thử lại</button>}
      {doc && <>
        <h3 className="admin-section-title">{doc.title}</h3>
        <p>Nguồn: <a href={doc.source_url} target="_blank" rel="noreferrer">{doc.source_id}</a> · Phiên bản: <strong>{doc.version}</strong></p>
        <p>Hiệu lực từ: {formatDate(utcStamp(doc.effective_at))} {formatTime(utcStamp(doc.effective_at))} · {doc.chunks.length} đoạn đã xử lý</p>
        <p><span className={`admin-badge ${doc.approved ? "success" : "pending"}`}>{doc.approved ? "Đã phê duyệt" : "Chờ phê duyệt"}</span></p>
        <div className="admin-doc-content">{doc.chunks.map((chunk) => chunk.content).join("\n\n") || "Chưa có nội dung đã xử lý."}</div>
        <footer><button disabled={busy} onClick={() => onEdit(doc)}>Chỉnh sửa</button>
          <button className="admin-primary" disabled={busy || !doc.chunks.length} onClick={() => approve(!doc.approved)}>{busy ? "Đang xử lý…" : doc.approved ? "Thu hồi phê duyệt" : "Phê duyệt phiên bản này"}</button></footer>
      </>}
    </div>
  </Dialog>;
}

export function DocumentsPage() {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [editor, setEditor] = useState(null);
  const [reviewId, setReviewId] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [notice, setNotice] = useState("");
  const list = useAdminData("/admin/documents", { q: query, offset, limit: 20 });
  const refresh = (message) => { list.reload(); setNotice(message); };
  return <>
    <PageHeading title="Tài liệu chatbot" description="Nhập tài liệu văn bản, kiểm tra nội dung và phê duyệt từng phiên bản. Chatbot chỉ tra cứu tài liệu đã duyệt và đến thời điểm hiệu lực."
      createLabel="Nhập tài liệu" onCreate={() => setEditor({})} />
    {notice && <p className="admin-notice" role="status">{notice}</p>}
    <section className="admin-panel">
      <div className="admin-toolbar"><Field label="Tìm tài liệu" type="search" placeholder="Tiêu đề hoặc mã nguồn" value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0); }} /></div>
      <DataTable columns={[
        { key: "title", label: "Tài liệu", render: (row) => <>{row.title}<small>{row.source_id}</small></> },
        { key: "version", label: "Phiên bản" },
        { key: "approved", label: "Phê duyệt", render: (row) => <span className={`admin-badge ${row.approved ? "success" : "pending"}`}>{row.approved ? "Đã duyệt" : "Chờ duyệt"}</span> },
        { key: "effective_at", label: "Hiệu lực từ", render: (row) => formatDate(utcStamp(row.effective_at)) },
        { key: "updated_at", label: "Cập nhật", render: (row) => formatDate(utcStamp(row.updated_at)) },
      ]} rows={list.data?.items} loading={list.loading} error={list.error} reload={list.reload} actions={(row) => <>
        <button onClick={() => setReviewId(row.id)}>Xem / duyệt</button><button className="admin-danger" onClick={() => setDeleting(row)}>Xóa</button></>} />
      <Pagination total={list.data?.total} offset={offset} onChange={setOffset} />
    </section>
    {reviewId && <DocumentReview documentId={reviewId} onClose={() => setReviewId(null)} onSaved={refresh} onEdit={(doc) => { setReviewId(null); setEditor(doc); }} />}
    {editor && <Editor title={editor.id ? "Cập nhật tài liệu" : "Nhập tài liệu tri thức"} onClose={() => setEditor(null)} submitLabel="Lưu & xử lý tài liệu"
      initial={{ source_id: editor.source_id || "", title: editor.title || "", version: editor.version || "1.0", source_url: editor.source_url || "/about",
        effective_at: localDateTime(editor.effective_at), content: editor.chunks?.map((chunk) => chunk.content).join("\n\n") || "" }}
      onSave={async (value) => {
        await api.post("/admin/documents", { ...value, effective_at: new Date(`${value.effective_at}:00+07:00`).toISOString(),
          ...(editor.id ? { expected_updated_at: utcStamp(editor.updated_at) } : {}) });
        refresh("Đã xử lý tài liệu. Phiên bản vừa lưu đang chờ phê duyệt.");
      }}>{(value, set, setValue) => <>
        <div className="admin-form-grid"><Field label="Mã nguồn tài liệu *" required disabled={!!editor.id} maxLength={100} value={value.source_id} onChange={set("source_id")} />
          <Field label="Phiên bản *" required maxLength={50} value={value.version} onChange={set("version")} /></div>
        <Field label="Tiêu đề *" required maxLength={200} value={value.title} onChange={set("title")} />
        <Field label="Đường dẫn nguồn * (HTTPS hoặc đường dẫn trong website)" required maxLength={500} value={value.source_url} onChange={set("source_url")} />
        <Field label="Thời điểm hiệu lực * (giờ Việt Nam)" required type="datetime-local" value={value.effective_at} onChange={set("effective_at")} />
        <Field label="Nhập từ tệp văn bản (.txt, .md; tối đa 200 KB)" type="file" accept=".txt,.md,text/plain,text/markdown" onChange={async (event) => {
          const file = event.target.files[0];
          if (!file) return;
          if (file.size > 200000) { event.target.setCustomValidity("Tệp không được vượt quá 200 KB"); event.target.reportValidity(); return; }
          event.target.setCustomValidity("");
          const content = await file.text(); setValue((old) => ({ ...old, content }));
        }} />
        <Field label="Nội dung tài liệu *" required type="textarea" maxLength={200000} value={value.content} onChange={set("content")} />
      </>}</Editor>}
    {deleting && <ConfirmAction title="Xóa tài liệu" description={`Xóa “${deleting.title}” cùng các đoạn tri thức? Chatbot sẽ ngừng truy xuất tài liệu này.`}
      onClose={() => setDeleting(null)} onConfirm={async () => {
        await api.delete(`/admin/documents/${deleting.id}`); setOffset(0); refresh("Đã xóa tài liệu khỏi kho tri thức.");
      }} />}
  </>;
}

function downloadReport(report) {
  const cell = (value) => `"${String(value).replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;
  const rows = [
    ["Báo cáo theo ngày chiếu", report.filters.start_date, report.filters.end_date],
    ["Thời điểm tổng hợp", report.as_of],
    ["Doanh thu (gồm đồ ăn)", report.revenue], ["Số đơn hợp lệ", report.booking_count],
    ["Vé đã phát hành / sử dụng", report.ticket_count], ["Ghế đã bán", report.occupied_seats],
    ["Tổng lượt ghế", report.seat_slots], ["Tỷ lệ sử dụng ghế (%)", report.occupancy],
    ["Đánh giá tích cực", report.sentiments.positive], ["Đánh giá trung lập", report.sentiments.neutral],
    ["Đánh giá tiêu cực", report.sentiments.negative], ["Chờ kết quả hợp lệ", report.sentiments.pending],
    ["Độ phủ phân tích (%)", report.sentiments.coverage], [], ["Phim", "Doanh thu", "Số đơn", "Số vé"],
    ...report.by_film.map((film) => [film.title, film.revenue, film.bookings, film.tickets]),
  ];
  const url = URL.createObjectURL(new Blob(["\uFEFF" + rows.map((row) => row.map(cell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `bao-cao-${report.filters.start_date}-${report.filters.end_date}.csv`;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ReportsPage() {
  const today = localDateInput();
  const [draft, setDraft] = useState({ start_date: `${today.slice(0, 7)}-01`, end_date: today, film_id: "", theater_id: "" });
  const [filters, setFilters] = useState(draft);
  const catalog = useAdminData("/admin/catalog");
  const report = useAdminData("/admin/reports", Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "")));
  const data = report.data;
  const set = (key) => (event) => setDraft((old) => ({ ...old, [key]: event.target.value }));
  return <>
    <PageHeading title="Báo cáo thống kê" description="Doanh thu, vé và tỷ lệ ghế theo ngày chiếu. Doanh thu gồm vé và đồ ăn, chỉ tính đơn xác nhận đã thanh toán hợp lệ." />
    <section className="admin-panel"><form className="admin-toolbar" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft }); report.reload(); }}>
      <Field label="Từ ngày *" required type="date" value={draft.start_date} max={draft.end_date} onChange={set("start_date")} />
      <Field label="Đến ngày *" required type="date" min={draft.start_date} value={draft.end_date} onChange={set("end_date")} />
      <Field label="Phim" value={draft.film_id} onChange={set("film_id")}><option value="">Tất cả phim</option>{catalog.data?.films.map((film) => <option key={film.id} value={film.id}>{film.title}</option>)}</Field>
      <Field label="Rạp" value={draft.theater_id} onChange={set("theater_id")}><option value="">Tất cả rạp</option>{catalog.data?.theaters.map((theater) => <option key={theater.id} value={theater.id}>{theater.name}</option>)}</Field>
      <button className="admin-primary" disabled={report.loading}>Xem báo cáo</button>
      {data && <button type="button" onClick={() => downloadReport(data)}>Xuất CSV</button>}
    </form>
      {(report.error || catalog.error) && <div><p className="admin-error" role="alert">{report.error || catalog.error}</p><button onClick={() => { report.reload(); catalog.reload(); }}>Thử lại</button></div>}
      {report.loading && <p role="status">Đang tổng hợp báo cáo…</p>}
      {data && <p className="text-xs text-gray-500">Phạm vi: {formatDate(data.filters.start_date)} – {formatDate(data.filters.end_date)} · Tổng hợp lúc {formatTime(data.as_of)} {formatDate(data.as_of)} (Việt Nam)</p>}
    </section>
    {data && <>
      <div className="admin-stats">
        <div className="admin-stat"><span>Doanh thu hợp lệ</span><strong>{formatCurrency(data.revenue)}</strong><small>{data.booking_count} đơn đã xác nhận</small></div>
        <div className="admin-stat"><span>Vé đã bán</span><strong>{data.ticket_count.toLocaleString("vi-VN")}</strong><small>Vé đã phát hành hoặc đã sử dụng</small></div>
        <div className="admin-stat"><span>Tỷ lệ sử dụng ghế</span><strong>{data.occupancy}%</strong><small>{data.occupied_seats} / {data.seat_slots} lượt ghế</small></div>
        <div className="admin-stat"><span>Độ phủ phân tích cảm xúc</span><strong>{data.sentiments.coverage}%</strong><small>{data.sentiments.total} đánh giá được duyệt</small></div>
      </div>
      <section className="admin-panel"><h2 className="admin-section-title">Doanh thu theo phim</h2>
        <DataTable columns={[{ key: "title", label: "Phim" }, { key: "revenue", label: "Doanh thu", render: (row) => formatCurrency(row.revenue) }, { key: "bookings", label: "Đơn hợp lệ" }, { key: "tickets", label: "Vé đã bán" }]}
          rows={data.by_film.map((film) => ({ ...film, id: film.film_id }))} />
      </section>
      <section className="admin-panel"><h2 className="admin-section-title">Cảm xúc đánh giá</h2>
        <p className="text-sm text-gray-500 mb-5">Theo thời điểm cập nhật đánh giá trong khoảng đã chọn; chỉ tính kết quả phân tích đúng phiên bản. Khi lọc rạp, lấy đánh giá của các phim chiếu tại rạp trong khoảng đó.</p>
        <div className="admin-sentiments"><span className="admin-badge success">Tích cực: {data.sentiments.positive}</span><span className="admin-badge">Trung lập: {data.sentiments.neutral}</span>
          <span className="admin-badge pending">Tiêu cực: {data.sentiments.negative}</span><span>Chờ kết quả hợp lệ: {data.sentiments.pending}</span></div>
      </section>
    </>}
  </>;
}
