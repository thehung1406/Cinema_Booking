import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageCircle, X } from 'lucide-react';
import { formatTime } from '../utils/formatters';
import api from '../config/api';
import { getAccessToken, AUTH_SESSION_CHANGED_EVENT } from '../services/authStorage';

export default function AIAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [context, setContext] = useState({});
  const [conversations, setConversations] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [hasMoreConversations, setHasMoreConversations] = useState(false);
  const [beforeId, setBeforeId] = useState(null);
  const [sessionVersion, setSessionVersion] = useState(0);
  const [films, setFilms] = useState([]);
  const [theaters, setTheaters] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loggedIn, setLoggedIn] = useState(Boolean(getAccessToken()));
  const bottom = useRef(null);
  const messageViewport = useRef(null);
  const historyScroll = useRef(null);
  const activeRequest = useRef(null);
  const historyRequest = useRef(null);
  const launcher = useRef(null);
  const panel = useRef(null);
  const restoreHistoryFocus = useRef(false);
  const location = useLocation();
  const inBookingFlow = /seat-selection|payment|booking|login/i.test(
    location.pathname,
  );
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);
  useEffect(() => {
    if (open) panel.current?.querySelector("button")?.focus();
  }, [open]);
  function close() {
    setOpen(false);
    launcher.current?.focus();
  }
  useLayoutEffect(() => {
    if (!busy && !conversationId && restoreHistoryFocus.current) {
      panel.current?.querySelector('#ai-conversation-history')?.focus();
      restoreHistoryFocus.current = false;
    }
  }, [busy, conversationId]);
  function reset() { activeRequest.current?.abort(); activeRequest.current = null; setBusy(false); setConversationId(null); setMessages([]); setContext({}); setBeforeId(null); setQuestion(''); setError(''); }
  useEffect(() => {
    const changed = () => {
      reset(); historyRequest.current?.abort(); setConversations([]); setHasMoreConversations(false);
      setLoggedIn(Boolean(getAccessToken())); setSessionVersion(v => v + 1);
    };
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, changed);
    window.addEventListener('storage', changed);
    return () => { window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, changed); window.removeEventListener('storage', changed); activeRequest.current?.abort(); historyRequest.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!open || !loggedIn) return;
    const controller = new AbortController(); historyRequest.current = controller;
    setHistoryBusy(true);
    api.get('/ai/conversations', { signal: controller.signal, params: { limit: 50 } })
      .then(({ data }) => {
        if (controller.signal.aborted) return;
        setConversations(data); setHasMoreConversations(data.length === 50);
      })
      .catch(e => { if (e.code !== 'ERR_CANCELED') setError('Chưa tải được lịch sử hội thoại.'); })
      .finally(() => { if (historyRequest.current === controller) setHistoryBusy(false); });
    return () => controller.abort();
  }, [open, loggedIn, sessionVersion]);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    Promise.all([api.get('/films/', { signal: controller.signal, params: { limit: 200 } }), api.get('/theaters', { signal: controller.signal })])
      .then(([f, t]) => { setFilms(f.data); setTheaters(t.data); })
      .catch(e => { if (e.code !== 'ERR_CANCELED') setError('Chưa tải được bộ lọc phim/rạp.'); });
    return () => controller.abort();
  }, [open]);
  useLayoutEffect(() => {
    if (historyScroll.current && messageViewport.current) {
      const { height, top } = historyScroll.current;
      messageViewport.current.scrollTop = top + messageViewport.current.scrollHeight - height;
      historyScroll.current = null;
    } else {
      bottom.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [messages]);
  async function send(event) {
    event.preventDefault(); if (busy || historyBusy || !question.trim()) return;
    const text = question.trim(); setBusy(true); setError('');
    const controller = new AbortController(); activeRequest.current = controller;
    try {
      const { data } = await api.post('/ai/chat', { message: text, conversation_id: conversationId, context }, { timeout: 25000, signal: controller.signal });
      if (controller.signal.aborted) return;
      setMessages(old => [...old, { role: 'user', answer: text }, { role: 'assistant', ...data }]);
      setConversationId(data.conversation_id); setContext(data.context); setQuestion('');
      setConversations(old => {
        const existing = old.find(c => c.id === data.conversation_id);
        return [{ ...existing, id: data.conversation_id, title: existing?.title || text.replace(/\s+/g, ' ').slice(0, 200),
          updated_at: data.as_of }, ...old.filter(c => c.id !== data.conversation_id)];
      });
    } catch (e) {
      if (e.code === 'ERR_CANCELED') return;
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Trợ lý đang bận. Vui lòng thử lại hoặc đặt vé trực tiếp.');
      if (e.response?.status === 404) {
        setConversations(old => old.filter(c => c.id !== conversationId));
        setConversationId(null); setMessages([]); setContext({}); setBeforeId(null);
      }
    } finally { if (activeRequest.current === controller) setBusy(false); }
  }
  async function loadConversation(id, older = false) {
    if (busy || historyBusy) return;
    if (!id) { reset(); return; }
    const controller = new AbortController(); activeRequest.current = controller;
    setBusy(true); setError('');
    try {
      const { data } = await api.get(`/ai/conversations/${id}`, {
        signal: controller.signal, params: { limit: 100, ...(older ? { before_id: beforeId } : {}) },
      });
      if (controller.signal.aborted) return;
      const loaded = data.messages.map(m => ({ ...m.metadata, id: m.id, role: m.role, answer: m.content }));
      if (older && messageViewport.current) {
        historyScroll.current = { height: messageViewport.current.scrollHeight, top: messageViewport.current.scrollTop };
      }
      setMessages(old => older ? [...loaded, ...old] : loaded);
      setBeforeId(data.next_before_id);
      if (!older) { setConversationId(data.id); setContext(data.context); setQuestion(''); }
    } catch (e) {
      if (e.code !== 'ERR_CANCELED') setError('Không thể tải hội thoại. Vui lòng thử lại.');
    } finally { if (activeRequest.current === controller) setBusy(false); }
  }
  async function loadMoreConversations() {
    if (busy || historyBusy) return;
    const controller = new AbortController(); historyRequest.current = controller;
    setHistoryBusy(true); setError('');
    try {
      const { data } = await api.get('/ai/conversations', {
        signal: controller.signal, params: { limit: 50, offset: conversations.length },
      });
      if (controller.signal.aborted) return;
      setConversations(old => [...old, ...data.filter(c => !old.some(item => item.id === c.id))]);
      setHasMoreConversations(data.length === 50);
    } catch (e) {
      if (e.code !== 'ERR_CANCELED') setError('Chưa tải được lịch sử hội thoại.');
    } finally { if (historyRequest.current === controller) setHistoryBusy(false); }
  }
  async function removeConversation() {
    if (busy || historyBusy || !conversationId) return;
    const id = conversationId;
    const controller = new AbortController(); activeRequest.current = controller;
    setBusy(true); setError('');
    try {
      await api.delete(`/ai/conversations/${id}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setConversations(old => old.filter(c => c.id !== id)); reset();
      restoreHistoryFocus.current = true;
    } catch (e) {
      if (e.code !== 'ERR_CANCELED') setError('Không thể xóa hội thoại. Vui lòng thử lại.');
    } finally { if (activeRequest.current === controller) setBusy(false); }
  }
  function choose(key, value) {
    setContext(old => ({ ...old, [key]: value || null, ...(key === 'showtime_id' ? {} : { showtime_id: null }) }));
  }
  return (
    <aside className={`assistant ${inBookingFlow ? "assistant-flow" : ""}`}>
      {open && (
        <section
          id="cinema-assistant"
          ref={panel}
          className="assistant-panel bg-white text-gray-900 rounded-xl border border-gray-200 shadow-2xl mb-3 flex flex-col"
          aria-label="Trợ lý Cinema"
          onKeyDown={(e) => {
            if (e.key === "Escape") close();
          }}
        >
          <header className="flex justify-between items-center bg-red-700 text-white rounded-t-xl px-4 py-2">
            <h2 className="font-bold flex items-center gap-2">
              <MessageCircle size={20} />
              Trợ lý Cinema
            </h2>
            <button className="btn" onClick={close} aria-label="Đóng trợ lý">
              <X size={20} />
            </button>
          </header>
          <div className="p-3 border-b text-sm space-y-2">
        {loggedIn && <div className="space-y-1">
          <label htmlFor="ai-conversation-history" className="block text-xs text-gray-600">Lịch sử hội thoại</label>
          <select id="ai-conversation-history" className="border rounded p-2 w-full" value={conversationId || ''}
            disabled={busy || historyBusy} onChange={e => loadConversation(e.target.value)}>
            <option value="">Hội thoại mới</option>
            {conversations.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
          {historyBusy && <p role="status" className="text-xs text-gray-500">Đang tải lịch sử…</p>}
          {conversationId && <button disabled={busy || historyBusy} onClick={() => loadConversation(conversationId)} className="text-xs text-red-700 underline mr-3">Tải lại hội thoại</button>}
          {hasMoreConversations && <button disabled={busy || historyBusy} onClick={loadMoreConversations} className="text-xs text-red-700 underline">Tải thêm hội thoại</button>}
        </div>}
            <p>Tra phim, lịch chiếu, giá vé và hướng dẫn đặt vé.</p>
            <div className="grid grid-cols-2 gap-2">
              <select
                aria-label="Phim cho trợ lý"
                className="border rounded p-2 min-w-0"
                value={context.film_id || ""}
                onChange={(e) => choose("film_id", Number(e.target.value))}
              >
                <option value="">Chọn phim</option>
                {films.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.title}
                  </option>
                ))}
              </select>
              <select
                aria-label="Rạp cho trợ lý"
                className="border rounded p-2 min-w-0"
                value={context.theater_id || ""}
                onChange={(e) => choose("theater_id", Number(e.target.value))}
              >
                <option value="">Chọn rạp</option>
                {theaters.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <input
                aria-label="Ngày xem cho trợ lý"
                type="date"
                className="border rounded p-2 min-w-0"
                value={context.show_date || ""}
                onChange={(e) => choose("show_date", e.target.value)}
              />
              <input
                aria-label="Mã suất chiếu"
                type="number"
                min="1"
                className="border rounded p-2 min-w-0"
                placeholder="Mã suất chiếu"
                value={context.showtime_id || ""}
                onChange={(e) => choose("showtime_id", Number(e.target.value))}
              />
            </div>
          </div>
          <div
            ref={messageViewport}
            className="overflow-y-auto p-3 space-y-3 min-h-0 flex-1"
            role="log"
            aria-live="polite"
          >
            {beforeId && <button disabled={busy || historyBusy} onClick={() => loadConversation(conversationId, true)} className="text-xs text-red-700 underline">Tải tin nhắn cũ hơn</button>}
            {!messages.length && (
              <p className="text-gray-500 text-sm">
                Thử hỏi: “Cách đặt vé?” hoặc “Phim nào được khen và có suất tối
                nay?”
              </p>
            )}
            {messages.map((m, i) => (
              <article
                key={m.id ? `message:${m.id}` : `local:${i}`}
                className={`rounded-lg p-3 ${m.role === "user" ? "bg-red-50 ml-5" : "bg-gray-50 mr-2"}`}
              >
                <p className="text-xs font-semibold mb-1">
                  {m.role === "user" ? "Bạn" : "Trợ lý"}
                </p>
                <p className="text-sm whitespace-pre-wrap break-words">
                  {m.answer}
                </p>
                {m.sources?.length > 0 && (
                  <details className="text-xs mt-2">
                    <summary className="cursor-pointer">
                      Nguồn tham chiếu ({m.sources.length})
                    </summary>
                    {m.sources.map((s) => (
                      <div key={s.id} className="mt-2">
                        <strong>
                          {s.title}
                          {s.version ? ` · ${s.version}` : ""}
                        </strong>
                        <p className="whitespace-pre-wrap break-words">
                          {s.text}
                        </p>
                      </div>
                    ))}
                  </details>
                )}
                {m.links?.map((l, j) => (
                  <Link
                    key={j}
                    to={l.url}
                    className="block text-sm text-red-700 underline mt-2"
                  >
                    {l.title} →
                  </Link>
                ))}
                {m.as_of && (
                  <p className="text-xs text-gray-500 mt-2">
                    Tra cứu lúc {formatTime(m.as_of)}
                  </p>
                )}
                {m.mode === "model_unavailable" && (
                  <p className="text-xs text-amber-700 mt-2">
                    Mô hình đang bận; hiển thị dữ liệu truy xuất trực tiếp.
                  </p>
                )}
              </article>
            ))}
            {busy && (
              <p className="text-sm" role="status">
                Đang xử lý…
              </p>
            )}
            <div ref={bottom} />
          </div>
          {error && (
            <p role="alert" className="text-red-700 px-3 text-sm">
              {error}
            </p>
          )}
          <div className="p-3 border-t">
            {loggedIn ? (
              <form onSubmit={send} className="flex gap-2">
                <input
                  aria-label="Câu hỏi cho trợ lý"
                  className="border rounded p-2 min-w-0 flex-1"
                  maxLength={2000}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Nhập câu hỏi…"
                  required
                />
                <button
                  className="bg-red-700 text-white px-3 rounded disabled:opacity-50"
                  disabled={busy || historyBusy || !question.trim()}
                >
                  Gửi
                </button>
              </form>
            ) : (
              <Link className="text-red-700 underline" to="/login">
                Đăng nhập để trò chuyện
              </Link>
            )}
            <div className="flex justify-between text-xs mt-3">
              <button disabled={busy || historyBusy} onClick={reset}>Hội thoại mới</button>
              {conversationId && <button disabled={busy || historyBusy} onClick={removeConversation} className="text-red-700">Xóa hội thoại</button>}
              <Link to="/ticket-booking" className="text-red-700 underline">
                Đặt vé trực tiếp
              </Link>
            </div>
          </div>
        </section>
      )}
      <button
        ref={launcher}
        onClick={() => (open ? close() : setOpen(true))}
        aria-expanded={open}
        aria-controls="cinema-assistant"
        className="assistant-launcher"
      >
        <MessageCircle size={20} aria-hidden="true" />
        {open ? "Thu gọn" : "Hỏi trợ lý"}
      </button>
    </aside>
  );
}
