import { useCallback, useEffect, useState } from 'react';
import api from '../config/api';
import { getCurrentUser } from '../services/authStorage';

export default function ReviewModeration() {
  const [reviews, setReviews] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const allowed = ['ADMIN', 'STAFF'].includes(getCurrentUser()?.role);
  const load = useCallback(() => api.get('/reviews/moderation/pending').then(r => setReviews(r.data)), []);
  useEffect(() => { if (allowed) load().catch(() => setError('Không tải được danh sách chờ duyệt.')); }, [allowed, load]);
  async function moderate(review, status) {
    setBusy(true); setError('');
    try { await api.patch(`/reviews/${review.id}/moderation`, { status, content_version: review.content_version }); await load(); }
    catch { setError('Không thể duyệt. Nội dung có thể đã thay đổi; hãy tải lại danh sách.'); await load().catch(() => {}); }
    finally { setBusy(false); }
  }
  if (!allowed) return <p className="p-8">Chức năng dành cho nhân viên kiểm duyệt.</p>;
  return <main className="max-w-4xl mx-auto p-6"><h1 className="text-2xl font-bold">Duyệt đánh giá</h1>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!reviews.length && <p className="py-6">Không có đánh giá đang chờ duyệt.</p>}
    {reviews.map(r => <article key={r.id} className="my-4 border rounded p-4"><p className="font-semibold">{r.author} · phiên bản {r.content_version}</p><p className="whitespace-pre-wrap break-words my-3">{r.content}</p><button disabled={busy} onClick={() => moderate(r, 'approved')} className="bg-green-700 text-white rounded px-4 py-2 mr-3">Duyệt</button><button disabled={busy} onClick={() => moderate(r, 'rejected')} className="text-red-700">Từ chối</button></article>)}
  </main>;
}
