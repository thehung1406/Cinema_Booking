import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';

export default function PositiveFilms() {
  const [films, setFilms] = useState([]);
  const [theaters, setTheaters] = useState([]);
  const [theater, setTheater] = useState('');
  const [date, setDate] = useState('');
  const [status, setStatus] = useState('loading');
  useEffect(() => {
    const controller = new AbortController();
    api.get('/theaters', { signal: controller.signal }).then(r => setTheaters(r.data)).catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setStatus('loading');
    api.get('/films/positive-trending', { signal: controller.signal, params: { theater_id: theater || undefined, show_date: date || undefined } })
      .then(r => { setFilms(r.data); setStatus('ready'); })
      .catch(e => { if (e.code !== 'ERR_CANCELED') setStatus('error'); });
    return () => controller.abort();
  }, [theater, date]);
  return <section className="max-w-7xl mx-auto my-10 px-4">
    <h2 className="text-2xl font-bold mb-2">Phim được đánh giá tích cực</h2>
    <p className="text-gray-600 mb-4">Phản hồi cộng đồng trong 30 ngày, xếp hạng có tính đến số lượng đánh giá và còn suất chiếu.</p>
    <div className="flex flex-wrap gap-3 mb-5">
      <select aria-label="Lọc theo rạp" value={theater} onChange={e => setTheater(e.target.value)} className="border rounded p-2">
        <option value="">Tất cả rạp</option>{theaters.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
      <input aria-label="Ngày xem" type="date" value={date} onChange={e => setDate(e.target.value)} className="border rounded p-2" />
    </div>
    {status === 'loading' && <p role="status">Đang tải phản hồi…</p>}
    {status === 'error' && <p role="alert">Chưa tải được danh sách. Bạn có thể chọn phim ở mục đang chiếu.</p>}
    {status === 'ready' && !films.length && <p className="bg-gray-50 border rounded-lg p-6">Chưa có phim đủ đánh giá hợp lệ và suất chiếu phù hợp.</p>}
    {status === 'ready' && <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{films.map(f => <Link key={f.film_id} to={`/movie/${f.film_id}`} className="rounded-xl border bg-white overflow-hidden hover:shadow-md">
      {f.image && <img className="w-full h-56 object-cover" src={f.image} alt={f.title} />}
      <div className="p-4"><h3 className="font-bold">{f.title}</h3><p className="text-green-700">{Math.round(f.summary.positive_ratio * 100)}% tích cực</p><p className="text-sm text-gray-500">{f.summary.total} đánh giá · {f.summary.window_days} ngày</p></div>
    </Link>)}</div>}
  </section>;
}
