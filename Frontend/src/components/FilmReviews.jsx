import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { getAccessToken } from '../services/authStorage';

const labels = { positive: 'Tích cực', neutral: 'Trung lập', negative: 'Tiêu cực' };
const statuses = { pending: 'Chờ phân tích', failed: 'Chưa phân tích được', needs_review: 'Cần rà soát', succeeded: 'Đã phân tích' };
const moderation = { pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Chưa được duyệt' };

export default function FilmReviews({ filmId }) {
  const [summary, setSummary] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [mine, setMine] = useState(null);
  const [content, setContent] = useState('');
  const [editVersion, setEditVersion] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);
  const loggedIn = Boolean(getAccessToken());
  const load = useCallback(async (signal) => {
    const [stats, list, own] = await Promise.all([
      api.get(`/films/${filmId}/sentiment-summary`, { signal }),
      api.get(`/films/${filmId}/reviews`, { signal, params: { skip: page * 20, limit: 20 } }),
      loggedIn ? api.get(`/films/${filmId}/reviews/mine`, { signal }) : Promise.resolve({ data: null }),
    ]);
    setSummary(stats.data); setReviews(list.data); setMine(own.data);
  }, [filmId, loggedIn, page]);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => load(controller.signal).catch((e) => {
      if (e.code !== 'ERR_CANCELED') setError('Chưa tải được đánh giá. Bạn vẫn có thể đặt vé.');
    });
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [load]);

  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      if (mine) await api.patch(`/reviews/${mine.id}`, { content, content_version: editVersion ?? mine.content_version });
      else await api.post(`/films/${filmId}/reviews`, { content });
      setContent(''); setEditVersion(null); setNotice('Đã lưu đánh giá. Kết quả sẽ xuất hiện sau khi duyệt và phân tích.');
      await load();
    } catch (e) {
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Không lưu được đánh giá.');
    } finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setError('');
    try { await api.delete(`/reviews/${mine.id}`); setContent(''); setEditVersion(null); await load(); }
    catch { setError('Không xóa được đánh giá. Vui lòng thử lại.'); }
    finally { setBusy(false); }
  }
  return <section className="mt-8 rounded-xl bg-white p-6 shadow" aria-labelledby="review-title">
    <h2 id="review-title" className="text-2xl font-bold mb-3">Cảm nhận của khán giả</h2>
    {summary && <>
      <p className="text-sm text-gray-600 mb-4">{summary.total} đánh giá hợp lệ trong {summary.window_days} ngày gần nhất · {summary.eligible ? 'Đủ dữ liệu xếp hạng' : `Chưa đủ đánh giá (cần ${summary.min_reviews})`}</p>
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(labels).map(([key, label]) => <div className="rounded-lg bg-gray-50 p-3" key={key}>
          <p>{label}</p><strong className="text-xl">{summary.total ? Math.round(summary[key] / summary.total * 100) : 0}%</strong>
          <span className="block text-sm text-gray-500">{summary[key]} đánh giá</span>
        </div>)}
      </div>
      <p className="text-sm text-gray-500 mt-2">Chờ xử lý: {summary.pending} · Cần rà soát: {summary.needs_review}. Các đánh giá này chưa được tính vào tỷ lệ.</p>
    </>}
    {error && <p role="alert" className="my-3 text-red-700">{error}</p>}
    {notice && <p role="status" className="my-3 text-green-700">{notice}</p>}
    {loggedIn ? <form onSubmit={save} className="my-6 space-y-3">
      {mine && <div className="bg-blue-50 rounded p-3">
        <p className="font-medium">Đánh giá của bạn · {moderation[mine.moderation_status]} · {statuses[mine.analysis_status]}</p>
        <p className="whitespace-pre-wrap break-words my-2">{mine.content}</p>
        <button type="button" className="text-blue-700 mr-4 underline" disabled={busy} onClick={() => { setContent(mine.content); setEditVersion(mine.content_version); }}>Chỉnh sửa</button>
        <button type="button" className="text-red-700 underline" disabled={busy} onClick={remove}>Xóa đánh giá</button>
      </div>}
      <label className="block font-medium" htmlFor="review-content">{mine ? 'Cập nhật cảm nhận' : 'Viết cảm nhận về phim'}</label>
      <textarea id="review-content" value={content} onChange={e => { if (mine && editVersion === null) setEditVersion(mine.content_version); setContent(e.target.value); }} minLength={5} maxLength={3000} required rows={3} className="w-full border rounded p-3" placeholder="Bạn thấy nội dung, diễn xuất của phim như thế nào?" />
      <button disabled={busy || content.trim().length < 5} className="bg-red-600 text-white px-5 py-2 rounded disabled:opacity-50">{busy ? 'Đang lưu…' : mine ? 'Lưu chỉnh sửa' : 'Gửi đánh giá'}</button>
      <p className="text-sm text-gray-500">Mỗi tài khoản có một đánh giá cho mỗi phim. Nội dung chỉnh sửa cần được duyệt lại.</p>
    </form> : <p className="my-6"><Link className="text-red-700 underline" to="/login">Đăng nhập</Link> để viết đánh giá.</p>}
    <div className="divide-y">
      {reviews.map(review => <article className="py-4" key={review.id}>
        <p className="font-semibold">{review.author} {review.verified_purchase && <span className="text-green-700 text-sm">· Đã mua vé</span>}</p>
        <p className="whitespace-pre-wrap break-words my-2">{review.content}</p>
        <p className="text-sm text-gray-500">{labels[review.sentiment] || statuses[review.analysis_status]} · {new Date(review.updated_at).toLocaleDateString('vi-VN')}</p>
      </article>)}
      {!reviews.length && <p className="py-4 text-gray-500">Chưa có đánh giá được duyệt.</p>}
    </div>
    <div className="flex gap-4 mt-3">
      <button disabled={!page} onClick={() => setPage(p => p - 1)} className="disabled:opacity-40">Trang trước</button>
      <button disabled={reviews.length < 20} onClick={() => setPage(p => p + 1)} className="disabled:opacity-40">Trang sau</button>
    </div>
  </section>;
}
