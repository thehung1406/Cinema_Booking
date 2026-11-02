import { useEffect, useState } from "react";
import api from "../../config/api";
import { formatCurrency } from "../../utils/formatters";

const reasons = {
  PAID_UNCONFIRMED: "Đã thu tiền, chưa có xác nhận vé",
  EVENT_BLOCKED: "Xác nhận vé bị kẹt sau nhiều lần thử",
  AMOUNT_MISMATCH: "Số tiền provider khác tổng đơn",
  DUPLICATE_PAYMENT: "Nhiều giao dịch đã thu tiền cho cùng đơn",
  ADDITIONAL_COLLECTION: "Có thêm kết quả thu tiền khác trên giao dịch",
  BOOKING_REJECTED: "Không thể xác nhận vé",
  PROVIDER_REFERENCE_CONFLICT: "Tham chiếu thu tiền trùng giao dịch khác",
  LEGACY_RECONCILIATION_REQUIRED: "Giao dịch cũ cần xác minh chứng từ và vé",
};

export default function PaymentReconciliation() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setError(""); setData(null);
    api.get("/admin/payment-reconciliation", { params: { offset, limit: 25 }, signal: controller.signal })
      .then(r => setData(r.data)).catch(e => {
        if (e.code !== "ERR_CANCELED") setError("Không tải được hồ sơ đối soát. Vui lòng thử lại.");
      });
    return () => controller.abort();
  }, [offset, attempt]);
  async function retry(event) {
    event.preventDefault();
    if (busy || !reason.trim() || !selected) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const r = await api.post(`/admin/payment-reconciliation/${selected.id}/retry`, { reason: reason.trim() });
      setNotice(r.data.queued ? "Đã yêu cầu thử xác nhận lại. Hồ sơ chỉ đóng khi có kết quả hợp lệ; tiền chưa được hoàn." : "Đã ghi nhận yêu cầu kiểm tra. Giao dịch cần xác minh chứng từ và vé trước khi xử lý tiền.");
      setSelected(null); setReason(""); setAttempt(v => v + 1);
    } catch { setError("Chưa gửi được yêu cầu. Giữ nguyên hồ sơ và thử lại."); }
    finally { setBusy(false); }
  }
  return <section className="admin-panel">
    <h1>Đối soát thanh toán</h1>
    <p>Các khoản thu cần kiểm tra vé hoặc chứng từ provider. Xác minh giao dịch và liên hệ khách trước khi xử lý tiền.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <button onClick={() => setAttempt(v => v + 1)}>Tải lại hồ sơ</button>
    {!data ? <p role="status">Đang tải đối soát…</p> : <>
      <p>{data.total} hồ sơ đang mở</p>
      {data.items.length === 0 ? <p>Không có hồ sơ trong trang này.</p> : <div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr><th>Giao dịch / Đơn</th><th>Vấn đề</th><th>Số tiền</th><th>Tham chiếu</th><th>Phát hiện</th><th>Thao tác</th></tr></thead>
        <tbody>{data.items.map(row => <tr key={row.id}>
          <td>{row.payment_id} / {row.booking_id || "—"}</td><td>{reasons[row.reason] || "Cần kiểm tra"}</td>
          <td>{formatCurrency(row.expected_amount)}{row.detail?.collected && <p>Đã thu: {formatCurrency(row.detail.collected)}</p>}</td>
          <td className="break-all">{row.merchant_ref || row.reference || "—"}<p>{row.transaction_ref}</p></td>
          <td>{new Date(row.created_at).toLocaleString("vi-VN")}</td>
          <td><button onClick={() => { setSelected(row); setReason(""); }}>Thử xác nhận lại #{row.payment_id}</button></td>
        </tr>)}</tbody>
      </table></div>}
      <div className="flex gap-3 mt-4"><button disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 25))}>Trang trước</button>
        <button disabled={offset + 25 >= data.total} onClick={() => setOffset(v => v + 25)}>Trang sau</button></div>
    </>}
    {selected && <form onSubmit={retry} className="mt-5">
      <label>Lý do thử xác nhận giao dịch #{selected.payment_id}<textarea required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} className="block w-full border p-3" /></label>
      <button disabled={busy || !reason.trim()} type="submit">{busy ? "Đang gửi…" : "Ghi nhận lý do và thử lại"}</button>
      <button type="button" disabled={busy} onClick={() => setSelected(null)}>Đóng</button>
    </form>}
  </section>;
}
