import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../config/api';
import { getCurrentUser } from '../services/authStorage';

const LABELS = { positive: 'Tích cực', neutral: 'Trung lập', negative: 'Tiêu cực' };

function SentimentDecision({ item, onSaved }) {
  const [label, setLabel] = useState(item.label || 'neutral');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(null);
  async function save(event) {
    event.preventDefault();
    const payload = { content_version: item.content_version, analysis_generation: item.analysis_generation,
      expected_updated_at: item.updated_at, label, reason: reason.trim() };
    const signature = JSON.stringify(payload);
    if (request.current?.signature !== signature) request.current = { signature, id: crypto.randomUUID() };
    setBusy(true); setError('');
    try {
      await api.post(`/reviews/${item.review_id}/sentiment-decision`, { ...payload, request_id: request.current.id });
      await onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || 'Chưa lưu được quyết định. Có thể thử lại cùng yêu cầu.');
    } finally { setBusy(false); }
  }
  return <article className="my-4 rounded-xl border border-gray-200 p-4 space-y-3">
    <p className="text-sm text-gray-500">Phim #{item.film_id} · đánh giá #{item.review_id} · phiên bản {item.content_version}</p>
    <p className="whitespace-pre-wrap">{item.content}</p>
    <p>Model: {item.model_version || 'Chưa có kết quả'} · dự đoán: {LABELS[item.predicted_label] || 'Chưa xác định'}</p>
    <div className="flex gap-3 flex-wrap text-sm">{Object.entries(item.scores || {}).map(([key, value]) =>
      <span key={key}>{LABELS[key] || key}: {(Number(value) * 100).toFixed(1)}%</span>)}</div>
    <p className="text-xs text-gray-500">Điểm số của mô hình là thông tin tham khảo. Xác nhận của nhân viên được lưu riêng và không thay đổi điểm dự đoán.</p>
    {item.decision_source === 'staff' && <p className="text-sm">Nhãn đã được nhân viên xác nhận: {LABELS[item.label]}</p>}
    <form onSubmit={save} className="space-y-2">
      <label className="block">Nhãn xác nhận
        <select className="border rounded p-2 ml-3" value={label} onChange={e => setLabel(e.target.value)} disabled={busy}>
          {Object.entries(LABELS).map(([key, text]) => <option key={key} value={key}>{text}</option>)}
        </select>
      </label>
      <label className="block">Lý do xác nhận hoặc sửa nhãn
        <textarea className="block border rounded p-2 w-full" value={reason} minLength={3} maxLength={1000}
          onChange={e => setReason(e.target.value)} required disabled={busy} />
      </label>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <button className="bg-red-700 text-white rounded px-4 py-2" disabled={busy || reason.trim().length < 3}>
        {busy ? 'Đang lưu…' : 'Lưu nhãn xác nhận'}
      </button>
    </form>
  </article>;
}

function SentimentDemo() {
  const [content, setContent] = useState('');
  const [predictions, setPredictions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function compare(event) {
    event.preventDefault();
    setBusy(true); setError(''); setPredictions([]);
    try {
      const { data } = await api.post('/reviews/sentiment/demo', { content: content.trim() }, { timeout: 65000 });
      setPredictions(data.predictions);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Không chạy được phép so sánh.');
    } finally { setBusy(false); }
  }
  return <section className="my-4 border rounded p-4 space-y-3">
    <h2 className="font-semibold">So sánh mô hình cảm xúc</h2>
    <p className="text-sm text-gray-600">Hai mô hình thử nghiệm trên nhãn silver. Kết quả chỉ hiển thị trong lượt thử.</p>
    <form onSubmit={compare} className="space-y-2">
      <label className="block">Nội dung review phim
        <textarea className="block border rounded p-2 w-full" required minLength={5} maxLength={3000} disabled={busy}
          value={content} onChange={e => { setContent(e.target.value); setPredictions([]); setError(''); }} />
      </label>
      <button className="bg-red-700 text-white rounded px-4 py-2" disabled={busy || content.trim().length < 5}>
        {busy ? 'Đang chạy hai mô hình…' : 'So sánh hai mô hình'}
      </button>
    </form>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {predictions.map(item => <article key={item.model} className="border rounded p-3">
      <h3 className="font-semibold">{item.model} · {LABELS[item.label]}</h3>
      <p className="text-sm">{item.model_version}{item.needs_review ? ' · Cần rà soát' : ''}</p>
      <div className="flex flex-wrap gap-3 text-sm">{Object.entries(item.scores).map(([label, score]) =>
        <span key={label}>{LABELS[label]} {(Number(score) * 100).toFixed(1)}%</span>)}</div>
    </article>)}
  </section>;
}

export default function ReviewModeration() {
  const [reviews, setReviews] = useState([]);
  const [tab, setTab] = useState('content');
  const [status, setStatus] = useState('needs_review');
  const [sentiments, setSentiments] = useState([]);
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const user = getCurrentUser();
  const allowed = user?.permissions?.includes('reviews.moderate') || ['ADMIN', 'STAFF'].includes(user?.role);
  const load = useCallback(async () => {
    if (tab === 'content') {
      const response = await api.get('/reviews/moderation/pending'); setReviews(response.data);
    } else {
      const response = await api.get('/reviews/sentiment/pending', { params: { status, offset, limit: 20 } });
      setSentiments(response.data.items); setTotal(response.data.total); setDemoEnabled(response.data.demo_enabled === true);
    }
  }, [tab, status, offset]);
  useEffect(() => { if (allowed) load().catch(() => setError('Không tải được danh sách chờ duyệt.')); }, [allowed, load]);
  async function moderate(review, status) {
    setBusy(true); setError('');
    try { await api.patch(`/reviews/${review.id}/moderation`, { status, content_version: review.content_version }); await load(); }
    catch { setError('Không thể duyệt. Nội dung có thể đã thay đổi; hãy tải lại danh sách.'); await load().catch(() => {}); }
    finally { setBusy(false); }
  }
  if (!allowed) return <p className="p-8">Chức năng dành cho nhân viên kiểm duyệt.</p>;
  return <main className="max-w-4xl mx-auto p-6"><h1 className="text-2xl font-bold">Duyệt đánh giá</h1>
    <div className="flex gap-3 my-5" role="tablist" aria-label="Loại rà soát">
      <button role="tab" aria-selected={tab === 'content'} onClick={() => { setTab('content'); setOffset(0); }}>Nội dung chờ duyệt</button>
      <button role="tab" aria-selected={tab === 'sentiment'} onClick={() => { setTab('sentiment'); setOffset(0); }}>Nhãn cảm xúc</button>
    </div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <button className="underline text-red-700" disabled={busy} onClick={() => load().catch(() => setError('Không tải được danh sách.'))}>Tải lại danh sách</button>
    {tab === 'content' ? <>
    {!reviews.length && <p className="py-6">Không có đánh giá đang chờ duyệt.</p>}
    {reviews.map(r => <article key={r.id} className="my-4 border rounded p-4"><p className="font-semibold">{r.author} · phiên bản {r.content_version}</p><p className="whitespace-pre-wrap break-words my-3">{r.content}</p><button disabled={busy} onClick={() => moderate(r, 'approved')} className="bg-green-700 text-white rounded px-4 py-2 mr-3">Duyệt</button><button disabled={busy} onClick={() => moderate(r, 'rejected')} className="text-red-700">Từ chối</button></article>)}
    </> : <>
      {demoEnabled && <SentimentDemo />}
      <label className="block my-4">Trạng thái
        <select className="border rounded p-2 ml-3" value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}>
          <option value="needs_review">Cần rà soát</option><option value="succeeded">Đã có nhãn hiệu lực</option>
        </select>
      </label>
      {!sentiments.length && <p>Không có đánh giá ở trạng thái này.</p>}
      {sentiments.map(item => <SentimentDecision key={`${item.review_id}:${item.updated_at}`} item={item} onSaved={load} />)}
      <div className="flex justify-between mt-4">
        <button disabled={offset === 0 || busy} onClick={() => setOffset(v => Math.max(0, v - 20))}>Trang trước</button>
        <span>{total} kết quả</span>
        <button disabled={offset + 20 >= total || busy} onClick={() => setOffset(v => v + 20)}>Trang sau</button>
      </div>
    </>}
  </main>;
}
