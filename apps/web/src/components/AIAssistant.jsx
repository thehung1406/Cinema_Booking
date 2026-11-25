import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, BookOpen, CalendarDays, ChevronDown, Film, History, MapPin, MessageCircle, Send, SlidersHorizontal, SquarePen, Ticket, X } from 'lucide-react';
import { formatCurrency, formatDate, formatTime } from '../utils/formatters';
import api from '../config/api';
import { getAccessToken, getCurrentUser, AUTH_SESSION_CHANGED_EVENT } from '../services/authStorage';
import { bookingCommand, showtimeAtOrdinal } from '../services/chatBooking';
import ChatBooking from './ChatBooking';
import './AIAssistant.css';

const SUGGESTIONS = [
  { icon: <Film size={20} aria-hidden="true" />, label: 'Gợi ý phim tối nay', detail: 'Tìm phim và suất chiếu phù hợp', question: 'Tối nay có phim hài nào còn suất chiếu cho hai người?' },
  { icon: <Ticket size={20} aria-hidden="true" />, label: 'Cách đặt vé', detail: 'Chọn suất, chọn ghế và thanh toán', question: 'Tôi đặt vé trên website như thế nào?' },
  { icon: <BookOpen size={20} aria-hidden="true" />, label: 'Hỏi về điện ảnh', detail: 'Thể loại, câu chuyện và góc máy', question: 'Cinematography là gì?' },
];

function readDraft(userId) {
  if (!userId) return null;
  try {
    const draft = JSON.parse(sessionStorage.getItem(`chat-booking:${userId}`));
    return Number.isSafeInteger(draft?.showtimeId) && draft.showtimeId > 0 ? draft : null;
  } catch { return null; }
}

function ShowtimeCard({ card, onNavigate, onBook }) {
  return (
    <section className="assistant-showtime">
      <div className="assistant-showtime-info">
        <h3>{card.film_title}</h3>
        <p><MapPin size={15} aria-hidden="true" /> <span>{[card.theater_name, card.room_name].filter(Boolean).join(' · ')}</span></p>
        <p><CalendarDays size={15} aria-hidden="true" /> <span>{formatTime(card.start_time)} · {formatDate(card.show_date)}{card.format && ` · ${card.format}`}</span></p>
      </div>
      <div className="assistant-showtime-price">
        <span>{card.party_size} vé từ</span>
        <strong>{formatCurrency(card.minimum_total)}</strong>
        <span>{formatCurrency(card.min_ticket_price)}/vé</span>
      </div>
      <div className="assistant-showtime-footer">
        <p><strong>{card.available_seats} ghế trống lúc tra cứu.</strong> Chưa giữ ghế hoặc xác nhận ghế liền nhau.</p>
        <Link to={card.url} className="assistant-primary" onClick={onNavigate}>Chọn ghế <ArrowRight size={16} aria-hidden="true" /></Link>
        <button type="button" className="assistant-direct-link" onClick={() => onBook(card)}>Đặt trong chat</button>
      </div>
    </section>
  );
}

function AssistantMessage({ message, onNavigate, onBook }) {
  const sourcesPanel = useRef(null);
  const cards = message.cards || [];
  const booking = message.booking;
  const documents = (message.sources || []).filter(source => source.kind === 'document');
  const links = (message.links || []).filter(link => !cards.some(card => card.url === link.url));
  const segments = message.answer?.split(/(\[doc:[^\]\r\n]+\])/g) || [];
  const documentsByReference = new Map(documents.map(source => [`[${source.id}]`, source]));
  const citedDocuments = segments.map(segment => documentsByReference.get(segment)).filter(Boolean);
  const groups = new Map();
  const citationNumbers = new Map();
  for (const source of citedDocuments.length ? citedDocuments : documents) {
    const key = JSON.stringify([source.source_id || source.title, source.version, source.url, source.provenance?.page_start]);
    if (!groups.has(key)) groups.set(key, { source, number: groups.size + 1, excerpts: new Set() });
    const group = groups.get(key);
    citationNumbers.set(`[${source.id}]`, group.number);
    if (source.text) group.excerpts.add(source.text);
  }

  function showSource(number) {
    sourcesPanel.current.open = true;
    sourcesPanel.current.querySelector(`[data-source-number="${number}"]`)?.focus();
  }

  return (
    <article className="assistant-message">
      <h3 className="assistant-message-author"><MessageCircle size={15} aria-hidden="true" /> Trợ lý Cinema</h3>
      <p className="assistant-answer">{segments.map((segment, index) => {
        const reference = citationNumbers.get(segment);
        return reference ? <button type="button" className="assistant-citation" key={index}
          aria-label={`Xem nguồn ${reference}`} onClick={() => showSource(reference)}>{reference}</button> : segment;
      })}</p>
      {booking && <section className="assistant-booking" aria-label="Thông tin đơn của bạn">
        <h4>Đơn #{booking.booking_id}{booking.film_title && ` · ${booking.film_title}`}</h4>
        <p>{[booking.theater_name, booking.show_date && formatDate(booking.show_date), booking.start_time && formatTime(booking.start_time)].filter(Boolean).join(' · ')}</p>
        <p>{booking.seat_count} vé · {formatCurrency(booking.total_amount)}</p>
        {booking.ticket_url === `/payment-result?bookingId=${booking.booking_id}` &&
          <Link className="assistant-primary" to={booking.ticket_url} onClick={onNavigate}>Xem vé</Link>}
      </section>}
      {cards.length > 0 && <div className="assistant-showtimes">
        {cards.map(card => <ShowtimeCard key={card.showtime_id} card={card} onNavigate={onNavigate} onBook={onBook} />)}
      </div>}
      {message.has_more && <p className="assistant-note">Còn suất khác. Thêm rạp, giờ hoặc ngân sách để thu hẹp kết quả.</p>}
      {links.length > 0 && <div className="assistant-message-links">
        {links.map(link => <Link key={link.url + link.title} to={link.url} onClick={onNavigate}>
          {link.title} <ArrowUpRight size={15} aria-hidden="true" />
        </Link>)}
      </div>}
      {groups.size > 0 && (
        <details className="assistant-sources" ref={sourcesPanel}>
          <summary><BookOpen size={17} aria-hidden="true" /> <span>Nguồn tham chiếu ({groups.size})</span><ChevronDown size={16} aria-hidden="true" /></summary>
          <ol>
            {Array.from(groups.values(), ({ source, number, excerpts }) => (
              <li key={source.id}>
                <span className="assistant-source-number" aria-hidden="true">{number}</span>
                <div className="assistant-source-body">
                  <h4 tabIndex={-1} data-source-number={number}>{source.title}</h4>
                  {source.version && <p className="assistant-note">Phiên bản {source.version}</p>}
                  {excerpts.size > 0 && <details className="assistant-source-excerpt">
                    <summary>Xem trích đoạn</summary>
                    {Array.from(excerpts, excerpt => <p key={excerpt}>{excerpt}</p>)}
                  </details>}
                  <a href={source.url} target="_blank" rel="noreferrer">
                    Mở nguồn{source.provenance?.page_start ? ` · trang PDF ${source.provenance.page_start}` : ''}
                    <ArrowUpRight size={14} aria-hidden="true" />
                  </a>
                </div>
              </li>
            ))}
          </ol>
        </details>
      )}
      <div className="assistant-message-meta">
        {message.as_of && <span>Tra cứu lúc {formatTime(message.as_of)}</span>}
        {message.mode === 'model_unavailable' && message.sources?.length > 0 && <span>Mô hình đang bận. Đang hiển thị dữ liệu truy xuất trực tiếp.</span>}
      </div>
    </article>
  );
}

export default function AIAssistant() {
  const [open, setOpen] = useState(false);
  const [tool, setTool] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState('');
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
  const userId = loggedIn ? getCurrentUser()?.id : null;
  const [bookingDraft, setBookingDraft] = useState(() => readDraft(getCurrentUser()?.id));
  const bookingDraftRef = useRef(bookingDraft);
  const composer = useRef(null);
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
    setTool(null);
  }, [location.pathname]);
  useLayoutEffect(() => {
    if (!open || !panel.current) return;
    if (!panel.current.open) panel.current.showModal();
  }, [open]);
  function dismiss() {
    setOpen(false);
    setTool(null);
  }
  function close() {
    dismiss();
    requestAnimationFrame(() => launcher.current?.focus({ preventScroll: true }));
  }
  useLayoutEffect(() => {
    if (!busy && !conversationId && restoreHistoryFocus.current) {
      panel.current?.querySelector('#ai-conversation-history')?.focus();
      restoreHistoryFocus.current = false;
    }
  }, [busy, conversationId]);
  function reset() { activeRequest.current?.abort(); activeRequest.current = null; setBusy(false); setConversationId(null); setMessages([]); setContext({}); setBeforeId(null); setQuestion(''); setPendingQuestion(''); setError(''); }
  useEffect(() => {
    const changed = () => {
      reset(); historyRequest.current?.abort(); setConversations([]); setHasMoreConversations(false);
      setLoggedIn(Boolean(getAccessToken())); setSessionVersion(v => v + 1);
      bookingDraftRef.current = readDraft(getCurrentUser()?.id);
      setBookingDraft(bookingDraftRef.current);
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
    if (!open || tool !== 'filters') return;
    const controller = new AbortController();
    Promise.all([api.get('/films/', { signal: controller.signal, params: { limit: 200 } }), api.get('/theaters', { signal: controller.signal })])
      .then(([f, t]) => { setFilms(f.data); setTheaters(t.data); })
      .catch(e => { if (e.code !== 'ERR_CANCELED') setError('Chưa tải được bộ lọc phim/rạp.'); });
    return () => controller.abort();
  }, [open, tool]);
  useLayoutEffect(() => {
    if (!messageViewport.current) return;
    if (historyScroll.current) {
      const { height, top } = historyScroll.current;
      messageViewport.current.scrollTop = top + messageViewport.current.scrollHeight - height;
      historyScroll.current = null;
    } else {
      messageViewport.current.scrollTop = messages.length || pendingQuestion || bookingDraft?.showtimeId ? messageViewport.current.scrollHeight : 0;
    }
  }, [open, messages, pendingQuestion, bookingDraft?.showtimeId]);

  function updateBooking(draft) {
    if (!userId || getCurrentUser()?.id !== userId) return;
    bookingDraftRef.current = draft;
    setBookingDraft(draft);
    try {
      const key = `chat-booking:${userId}`;
      if (draft) sessionStorage.setItem(key, JSON.stringify({ showtimeId: draft.showtimeId, partySize: draft.partySize, reservationId: draft.reservationId }));
      else sessionStorage.removeItem(key);
    } catch { /* Continue with the draft in this tab when storage is unavailable. */ }
  }

  function startBooking(card, seatNames = []) {
    const current = bookingDraftRef.current;
    if (!Number.isSafeInteger(card?.showtime_id) || card.showtime_id <= 0) {
      setError('Không có suất tương ứng trong danh sách gần nhất.');
      return false;
    }
    if (current && current.showtimeId !== card.showtime_id) {
      setError('Hãy đóng bước đặt vé hoặc hủy giữ ghế hiện tại trước khi chọn suất khác.');
      return false;
    }
    setError('');
    updateBooking({ ...current, showtimeId: card.showtime_id, partySize: card.party_size ?? current?.partySize,
      command: seatNames.length ? seatNames : current?.command });
    return true;
  }

  async function send(event) {
    event.preventDefault(); if (busy || historyBusy || !question.trim()) return;
    const text = question.trim();
    const command = bookingCommand(text);
    if (command) {
      const card = command.ordinal !== null ? showtimeAtOrdinal(messages, command.ordinal) : bookingDraft && { showtime_id: bookingDraft.showtimeId };
      if (!card && command.ordinal === null) setError('Hãy chọn một suất trước khi nhập tên ghế.');
      else if (startBooking(card, command.seatNames)) {
        setMessages(old => [...old, { role: 'user', answer: text }]);
        setQuestion('');
      }
      return;
    }
    setBusy(true); setPendingQuestion(text); setError('');
    const controller = new AbortController(); activeRequest.current = controller;
    try {
      const { data } = await api.post('/ai/chat', { message: text, conversation_id: conversationId, context }, { timeout: 30000, signal: controller.signal });
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
      const status = e.response?.status;
      if (conversationId && (status === 409 || e.code === 'ECONNABORTED')) {
        try {
          const { data } = await api.get(`/ai/conversations/${conversationId}`, {
            signal: controller.signal, params: { limit: 100 },
          });
          if (controller.signal.aborted) return;
          setMessages(data.messages.map(m => ({ ...m.metadata, id: m.id, role: m.role, answer: m.content })));
          setBeforeId(data.next_before_id);
          setContext(data.context);
          setError(e.code === 'ECONNABORTED'
            ? 'Yêu cầu quá thời gian chờ. Đã tải lại hội thoại để kiểm tra phản hồi mới nhất.'
            : 'Hội thoại vừa thay đổi và đã được tải lại. Bạn có thể gửi tiếp.');
          return;
        } catch {
          // Fall back to standard error handling if reloading fails.
        }
      }
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Trợ lý đang bận. Vui lòng thử lại hoặc đặt vé trực tiếp.');
      if (status === 404) {
        setConversations(old => old.filter(c => c.id !== conversationId));
        setConversationId(null); setMessages([]); setContext({}); setBeforeId(null);
      }
    } finally {
      if (activeRequest.current === controller) { setBusy(false); setPendingQuestion(''); }
    }
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
      if (!older) {
        setConversationId(data.id); setContext(data.context); setQuestion(''); setTool(null);
        requestAnimationFrame(() => messageViewport.current?.focus());
      }
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
  const selectedFilters = ['film_id', 'theater_id', 'show_date', 'showtime_id'].filter(key => context[key]).length;
  const controlsDisabled = busy || historyBusy;

  function startConversation() {
    reset();
    setTool(null);
    composer.current?.focus();
  }

  function chooseSuggestion(text) {
    setQuestion(text);
    composer.current?.focus();
  }

  return (
    <aside className={`assistant${inBookingFlow ? ' assistant-flow' : ''}`}>
      {open && (
        <dialog id="cinema-assistant" ref={panel} className="assistant-panel"
          aria-labelledby="cinema-assistant-title" onCancel={event => { event.preventDefault(); close(); }}>
          <div className="assistant-shell">
            <header className="assistant-header">
              <div className="assistant-identity">
                <span className="assistant-brand-icon"><Ticket size={24} aria-hidden="true" /></span>
                <div className="assistant-title-block">
                  <h2 id="cinema-assistant-title">Trợ lý Cinema</h2>
                  <p>Phim, lịch chiếu và vé của bạn</p>
                </div>
              </div>
              <div className="assistant-header-actions">
                {loggedIn && <button type="button" className="assistant-new" onClick={startConversation}
                  disabled={controlsDisabled} aria-label="Hội thoại mới" title="Hội thoại mới">
                  <SquarePen size={17} aria-hidden="true" /><span>Hội thoại mới</span>
                </button>}
                <button type="button" className="assistant-close" onClick={close} aria-label="Đóng trợ lý">
                  <X size={22} aria-hidden="true" />
                </button>
              </div>
            </header>

            {loggedIn && <nav className="assistant-toolbar" aria-label="Công cụ trò chuyện">
              <button type="button" aria-expanded={tool === 'history'} aria-controls="assistant-tools"
                onClick={() => setTool(tool === 'history' ? null : 'history')}>
                <History size={17} aria-hidden="true" /> Lịch sử
              </button>
              <button type="button" aria-expanded={tool === 'filters'} aria-controls="assistant-tools"
                onClick={() => setTool(tool === 'filters' ? null : 'filters')}>
                <SlidersHorizontal size={17} aria-hidden="true" /> Bộ lọc
                {selectedFilters > 0 && <span className="assistant-filter-count">{selectedFilters}</span>}
              </button>
              <Link to="/ticket-booking" className="assistant-direct-link" onClick={dismiss}>
                Đặt vé <ArrowUpRight size={15} aria-hidden="true" />
              </Link>
            </nav>}

            <div className={`assistant-workspace${tool && loggedIn ? ' has-tools' : ''}`}>
              {tool === 'history' && loggedIn && (
                <section id="assistant-tools" className="assistant-tools" aria-labelledby="ai-conversation-history">
                  <h3 id="ai-conversation-history" tabIndex={-1}>Lịch sử hội thoại</h3>
                  {historyBusy && <p role="status" className="assistant-note">Đang tải lịch sử…</p>}
                  {!historyBusy && conversations.length === 0 && <p className="assistant-note">Chưa có hội thoại đã lưu.</p>}
                  <ul className="assistant-history-list">
                    {conversations.map(conversation => (
                      <li key={conversation.id}>
                        <button type="button" disabled={controlsDisabled}
                          aria-current={conversation.id === conversationId ? 'true' : undefined}
                          onClick={() => loadConversation(conversation.id)}>
                          <span>{conversation.title}</span>
                          {conversation.updated_at && <time dateTime={conversation.updated_at}>{formatDate(conversation.updated_at)}</time>}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {hasMoreConversations && <button type="button" className="assistant-text-button" disabled={controlsDisabled}
                    onClick={loadMoreConversations}>Tải thêm hội thoại</button>}
                  {conversationId && <div className="assistant-history-actions">
                    <button type="button" className="assistant-text-button" disabled={controlsDisabled}
                      onClick={() => loadConversation(conversationId)}>Tải lại hội thoại</button>
                    <button type="button" className="assistant-text-button assistant-danger" disabled={controlsDisabled}
                      onClick={removeConversation}>Xóa hội thoại</button>
                  </div>}
                </section>
              )}

              {tool === 'filters' && loggedIn && (
                <section id="assistant-tools" className="assistant-tools" aria-labelledby="assistant-filter-title">
                  <h3 id="assistant-filter-title">Bộ lọc suất chiếu</h3>
                  <div className="assistant-fields">
                    <label>Phim
                      <select aria-label="Phim cho trợ lý" value={context.film_id || ''} disabled={busy}
                        onChange={event => choose('film_id', Number(event.target.value))}>
                        <option value="">Chọn phim</option>
                        {films.map(film => <option key={film.id} value={film.id}>{film.title}</option>)}
                      </select>
                    </label>
                    <label>Rạp
                      <select aria-label="Rạp cho trợ lý" value={context.theater_id || ''} disabled={busy}
                        onChange={event => choose('theater_id', Number(event.target.value))}>
                        <option value="">Chọn rạp</option>
                        {theaters.map(theater => <option key={theater.id} value={theater.id}>{theater.name}</option>)}
                      </select>
                    </label>
                    <label>Ngày xem
                      <input aria-label="Ngày xem cho trợ lý" type="date" value={context.show_date || ''} disabled={busy}
                        onChange={event => choose('show_date', event.target.value)} />
                    </label>
                    <details className="assistant-advanced"><summary>Nâng cao</summary><label>Mã suất chiếu
                      <input aria-label="Mã suất chiếu" type="number" min="1" placeholder="Ví dụ 16"
                        value={context.showtime_id || ''} disabled={busy}
                        onChange={event => choose('showtime_id', Number(event.target.value))} />
                    </label></details>
                  </div>
                </section>
              )}

              <div className="assistant-transcript" ref={messageViewport} role="log" aria-label="Tin nhắn" tabIndex={-1}>
                {beforeId && <button type="button" disabled={controlsDisabled} onClick={() => loadConversation(conversationId, true)}
                  className="assistant-text-button">Tải tin nhắn cũ hơn</button>}
                {!messages.length && !pendingQuestion && !busy && (
                  <div className="assistant-welcome">
                    <div className="assistant-welcome-mark" aria-hidden="true"><Ticket size={32} /></div>
                    <p className="assistant-welcome-label">Trợ lý điện ảnh của bạn</p>
                    <h3>Buổi xem phim này,<br />bạn muốn xem gì?</h3>
                    <p>Tìm một bộ phim hợp gu, chọn suất chiếu hoặc hỏi về vé của bạn.</p>
                    {loggedIn && <div className="assistant-suggestions">
                      {SUGGESTIONS.map(({ icon, label, detail, question: suggestion }) => (
                        <button key={label} type="button" aria-label={label} onClick={() => chooseSuggestion(suggestion)}>
                          <span className="assistant-suggestion-icon">{icon}</span>
                          <span className="assistant-suggestion-copy"><strong>{label}</strong><span>{detail}</span></span>
                          <ArrowUpRight size={16} aria-hidden="true" />
                        </button>
                      ))}
                    </div>}
                  </div>
                )}
                {messages.map((message, index) => message.role === 'user'
                  ? <div className="assistant-user-message" key={message.id ? `saved:${message.id}` : `local:${index}`}>
                    <span className="sr-only">Bạn: </span><p>{message.answer}</p>
                  </div>
                  : <AssistantMessage key={message.id ? `saved:${message.id}` : `local:${index}`} message={message} onNavigate={dismiss} onBook={startBooking} />)}
                {pendingQuestion && <p className="assistant-user-message"><span className="sr-only">Bạn: </span>{pendingQuestion}</p>}
                {busy && <p className="assistant-loading" role="status"><span aria-hidden="true" />{pendingQuestion ? 'Đang tìm thông tin…' : 'Đang xử lý…'}</p>}
                {userId && bookingDraft && <ChatBooking key={`${userId}:${bookingDraft.showtimeId}`} draft={bookingDraft} userId={userId}
                  onReservation={reservationId => updateBooking({ ...bookingDraftRef.current, reservationId })}
                  onDiscard={() => updateBooking(null)} />}
              </div>
            </div>

            <footer className="assistant-composer">
              {error && <p role="alert" className="assistant-error">{error}</p>}
              {loggedIn ? (
                <>
                <label htmlFor="assistant-question" className="assistant-composer-label">Câu hỏi cho trợ lý</label>
                <form onSubmit={send}>
                  <textarea id="assistant-question" ref={composer} maxLength={2000} rows={2}
                    value={pendingQuestion ? '' : question} readOnly={busy}
                    onChange={event => setQuestion(event.target.value)} placeholder="Bạn muốn xem phim gì?" required
                    onKeyDown={event => {
                      if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                        event.preventDefault();
                        if (!controlsDisabled && question.trim()) event.currentTarget.form?.requestSubmit();
                      }
                    }} />
                  <button type="submit" className="assistant-primary" disabled={controlsDisabled || !question.trim()}>
                    Gửi <Send size={17} aria-hidden="true" />
                  </button>
                </form>
                <p className="assistant-composer-hint"><span>Phim · Suất chiếu · Đơn vé</span><span className="assistant-keyboard-tip">Enter để gửi · Shift + Enter xuống dòng</span></p>
                </>
              ) : <div className="assistant-guest-actions">
                <Link className="assistant-primary" to="/login" onClick={dismiss}>Đăng nhập để trò chuyện <ArrowRight size={16} aria-hidden="true" /></Link>
                <Link className="assistant-direct-link" to="/ticket-booking" onClick={dismiss}>Đặt vé <ArrowUpRight size={15} aria-hidden="true" /></Link>
              </div>}
            </footer>
          </div>
        </dialog>
      )}
      <button ref={launcher} onClick={() => setOpen(true)} aria-expanded={open} aria-controls="cinema-assistant"
        aria-haspopup="dialog" aria-label="Hỏi trợ lý" className="assistant-launcher">
        <span className="assistant-launcher-icon"><Ticket size={24} aria-hidden="true" /></span>
        <span className="assistant-launcher-copy"><strong>Hỏi trợ lý</strong><span>Phim hay, lịch chiếu & vé</span></span>
        <ArrowUpRight size={19} aria-hidden="true" className="assistant-launcher-arrow" />
      </button>
    </aside>
  );
}
