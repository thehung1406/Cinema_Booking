import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { getAccessToken, AUTH_SESSION_CHANGED_EVENT } from '../services/authStorage';

export default function AIAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [context, setContext] = useState({});
  const [films, setFilms] = useState([]);
  const [theaters, setTheaters] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loggedIn, setLoggedIn] = useState(Boolean(getAccessToken()));
  const bottom = useRef(null);
  const activeRequest = useRef(null);
  function reset() { activeRequest.current?.abort(); setBusy(false); setConversationId(null); setMessages([]); setContext({}); setError(''); }
  useEffect(() => {
    const changed = () => { reset(); setLoggedIn(Boolean(getAccessToken())); };
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, changed);
    window.addEventListener('storage', changed);
    return () => { window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, changed); window.removeEventListener('storage', changed); activeRequest.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    Promise.all([api.get('/films/', { signal: controller.signal, params: { limit: 200 } }), api.get('/theaters', { signal: controller.signal })])
      .then(([f, t]) => { setFilms(f.data); setTheaters(t.data); })
      .catch(e => { if (e.code !== 'ERR_CANCELED') setError('Chưa tải được bộ lọc phim/rạp.'); });
    return () => controller.abort();
  }, [open]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'nearest' }); }, [messages, busy]);
  async function send(event) {
    event.preventDefault(); if (busy || !question.trim()) return;
    const text = question.trim(); setBusy(true); setError('');
    const controller = new AbortController(); activeRequest.current = controller;
    try {
      const { data } = await api.post('/ai/chat', { message: text, conversation_id: conversationId, context }, { timeout: 25000, signal: controller.signal });
      setMessages(old => [...old, { role: 'user', answer: text }, { role: 'assistant', ...data }]);
      setConversationId(data.conversation_id); setContext(data.context); setQuestion('');
    } catch (e) {
      if (e.code === 'ERR_CANCELED') return;
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Trợ lý đang bận. Vui lòng thử lại hoặc đặt vé trực tiếp.');
      if (e.response?.status === 404) setConversationId(null);
    } finally { if (activeRequest.current === controller) setBusy(false); }
  }
  function choose(key, value) {
    setContext(old => ({ ...old, [key]: value || null, ...(key === 'showtime_id' ? {} : { showtime_id: null }) }));
  }
  return <aside className="fixed bottom-4 right-4 z-40">
    {open && <section className="bg-white text-gray-900 rounded-xl border shadow-2xl w-[calc(100vw-2rem)] sm:w-[420px] mb-3 flex flex-col max-h-[85dvh]" aria-label="Trợ lý Cinema">
      <header className="flex justify-between items-center bg-red-700 text-white rounded-t-xl p-4"><h2 className="font-bold">Trợ lý Cinema</h2><button onClick={() => setOpen(false)} aria-label="Đóng trợ lý">✕</button></header>
      <div className="p-3 border-b text-sm space-y-2">
        <p>Tra phim, lịch chiếu, giá vé và hướng dẫn đặt vé.</p>
        <div className="grid grid-cols-2 gap-2">
          <select aria-label="Phim cho trợ lý" className="border rounded p-2 min-w-0" value={context.film_id || ''} onChange={e => choose('film_id', Number(e.target.value))}><option value="">Chọn phim</option>{films.map(f => <option key={f.id} value={f.id}>{f.title}</option>)}</select>
          <select aria-label="Rạp cho trợ lý" className="border rounded p-2 min-w-0" value={context.theater_id || ''} onChange={e => choose('theater_id', Number(e.target.value))}><option value="">Chọn rạp</option>{theaters.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
          <input aria-label="Ngày xem cho trợ lý" type="date" className="border rounded p-2 min-w-0" value={context.show_date || ''} onChange={e => choose('show_date', e.target.value)} />
          <input aria-label="Mã suất chiếu" type="number" min="1" className="border rounded p-2 min-w-0" placeholder="Mã suất chiếu" value={context.showtime_id || ''} onChange={e => choose('showtime_id', Number(e.target.value))} />
        </div>
      </div>
      <div className="overflow-y-auto p-3 space-y-3 min-h-24" role="log" aria-live="polite">
        {!messages.length && <p className="text-gray-500 text-sm">Thử hỏi: “Cách đặt vé?” hoặc “Phim nào được khen và có suất tối nay?”</p>}
        {messages.map((m, i) => <article key={i} className={`rounded-lg p-3 ${m.role === 'user' ? 'bg-red-50 ml-5' : 'bg-gray-50 mr-2'}`}>
          <p className="text-xs font-semibold mb-1">{m.role === 'user' ? 'Bạn' : 'Trợ lý'}</p>
          <p className="text-sm whitespace-pre-wrap break-words">{m.answer}</p>
          {m.sources?.length > 0 && <details className="text-xs mt-2"><summary className="cursor-pointer">Nguồn tham chiếu ({m.sources.length})</summary>{m.sources.map(s => <div key={s.id} className="mt-2"><strong>{s.title}{s.version ? ` · ${s.version}` : ''}</strong><p className="whitespace-pre-wrap break-words">{s.text}</p></div>)}</details>}
          {m.links?.map((l, j) => <Link key={j} to={l.url} className="block text-sm text-red-700 underline mt-2">{l.title} →</Link>)}
          {m.as_of && <p className="text-xs text-gray-500 mt-2">Tra cứu lúc {new Date(m.as_of).toLocaleTimeString('vi-VN')}</p>}
          {m.mode === 'model_unavailable' && <p className="text-xs text-amber-700 mt-2">Mô hình đang bận; hiển thị dữ liệu truy xuất trực tiếp.</p>}
        </article>)}
        {busy && <p className="text-sm" role="status">Đang tra cứu…</p>}<div ref={bottom} />
      </div>
      {error && <p role="alert" className="text-red-700 px-3 text-sm">{error}</p>}
      <div className="p-3 border-t">
        {loggedIn ? <form onSubmit={send} className="flex gap-2"><input aria-label="Câu hỏi cho trợ lý" className="border rounded p-2 min-w-0 flex-1" maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Nhập câu hỏi…" required /><button className="bg-red-700 text-white px-3 rounded disabled:opacity-50" disabled={busy || !question.trim()}>Gửi</button></form> : <Link className="text-red-700 underline" to="/login">Đăng nhập để trò chuyện</Link>}
        <div className="flex justify-between text-xs mt-3"><button onClick={reset}>Hội thoại mới</button><Link to="/ticket-booking" className="text-red-700 underline">Đặt vé trực tiếp</Link></div>
      </div>
    </section>}
    <button onClick={() => setOpen(v => !v)} aria-expanded={open} className="float-right bg-red-700 hover:bg-red-800 text-white px-5 py-3 rounded-full shadow-lg">{open ? 'Thu gọn' : 'Hỏi trợ lý Cinema'}</button>
  </aside>;
}
