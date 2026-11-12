import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, BookOpen, CalendarDays, ChevronDown, Film, History, MapPin, MessageCircle, Send, SlidersHorizontal, SquarePen, Ticket, X } from 'lucide-react';
import { formatCurrency, formatDate, formatTime } from '../utils/formatters';
import api from '../config/api';
import { getAccessToken, AUTH_SESSION_CHANGED_EVENT } from '../services/authStorage';
import './AIAssistant.css';

const SUGGESTIONS = [
  { icon: <Film size={19} aria-hidden="true" />, label: 'Gợi ý phim tối nay', question: 'Tối nay có phim hài nào còn suất chiếu cho hai người?' },
  { icon: <Ticket size={19} aria-hidden="true" />, label: 'Cách đặt vé', question: 'Tôi đặt vé trên website như thế nào?' },
  { icon: <BookOpen size={19} aria-hidden="true" />, label: 'Hỏi về điện ảnh', question: 'Cinematography là gì?' },
];

function ShowtimeCard({ card, onNavigate }) {
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
      </div>
    </section>
  );
}

function AssistantMessage({ message, onNavigate }) {
  const sourcesPanel = useRef(null);
  const cards = message.cards || [];
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
      {cards.length > 0 && <div className="assistant-showtimes">
        {cards.map(card => <ShowtimeCard key={card.showtime_id} card={card} onNavigate={onNavigate} />)}
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
    if (messageViewport.current) messageViewport.current.scrollTop = messageViewport.current.scrollHeight;
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
      messageViewport.current.scrollTop = messageViewport.current.scrollHeight;
    }
  }, [messages, pendingQuestion]);
  async function send(event) {
    event.preventDefault(); if (busy || historyBusy || !question.trim()) return;
    const text = question.trim(); setBusy(true); setPendingQuestion(text); setError('');
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
                <span className="assistant-brand-icon"><MessageCircle size={24} aria-hidden="true" /></span>
                <h2 id="cinema-assistant-title">Trợ lý Cinema</h2>
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
                    <label>Mã suất chiếu
                      <input aria-label="Mã suất chiếu" type="number" min="1" placeholder="Ví dụ 16"
                        value={context.showtime_id || ''} disabled={busy}
                        onChange={event => choose('showtime_id', Number(event.target.value))} />
                    </label>
                  </div>
                </section>
              )}

              <div className="assistant-transcript" ref={messageViewport} role="log" aria-label="Tin nhắn" tabIndex={-1}>
                {beforeId && <button type="button" disabled={controlsDisabled} onClick={() => loadConversation(conversationId, true)}
                  className="assistant-text-button">Tải tin nhắn cũ hơn</button>}
                {!messages.length && !pendingQuestion && !busy && (
                  <div className="assistant-welcome">
                    <h3>Bạn muốn hỏi gì?</h3>
                    <p>Tra suất chiếu, giá vé, cách đặt vé hoặc tìm hiểu về điện ảnh.</p>
                    {loggedIn && <div className="assistant-suggestions">
                      {SUGGESTIONS.map(({ icon, label, question: suggestion }) => (
                        <button key={label} type="button" onClick={() => chooseSuggestion(suggestion)}>
                          {icon}<span>{label}</span><ArrowRight size={16} aria-hidden="true" />
                        </button>
                      ))}
                    </div>}
                  </div>
                )}
                {messages.map((message, index) => message.role === 'user'
                  ? <div className="assistant-user-message" key={message.id ? `saved:${message.id}` : `local:${index}`}>
                    <span className="sr-only">Bạn: </span><p>{message.answer}</p>
                  </div>
                  : <AssistantMessage key={message.id ? `saved:${message.id}` : `local:${index}`} message={message} onNavigate={dismiss} />)}
                {pendingQuestion && <p className="assistant-user-message"><span className="sr-only">Bạn: </span>{pendingQuestion}</p>}
                {busy && <p className="assistant-loading" role="status"><span aria-hidden="true" />{pendingQuestion ? 'Đang tìm thông tin…' : 'Đang xử lý…'}</p>}
              </div>
            </div>

            <footer className="assistant-composer">
              {error && <p role="alert" className="assistant-error">{error}</p>}
              {loggedIn ? (
                <form onSubmit={send}>
                  <textarea ref={composer} aria-label="Câu hỏi cho trợ lý" maxLength={2000} rows={2}
                    value={pendingQuestion ? '' : question} readOnly={busy}
                    onChange={event => setQuestion(event.target.value)} placeholder="Nhập câu hỏi…" required
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
              ) : <div className="assistant-guest-actions">
                <Link className="assistant-primary" to="/login" onClick={dismiss}>Đăng nhập để trò chuyện <ArrowRight size={16} aria-hidden="true" /></Link>
                <Link className="assistant-direct-link" to="/ticket-booking" onClick={dismiss}>Đặt vé <ArrowUpRight size={15} aria-hidden="true" /></Link>
              </div>}
            </footer>
          </div>
        </dialog>
      )}
      <button ref={launcher} onClick={() => setOpen(true)} aria-expanded={open} aria-controls="cinema-assistant"
        aria-haspopup="dialog" className="assistant-launcher">
        <MessageCircle size={20} aria-hidden="true" /> Hỏi trợ lý
      </button>
    </aside>
  );
}
