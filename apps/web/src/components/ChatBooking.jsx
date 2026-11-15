import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../config/api';
import { getCurrentUser } from '../services/authStorage';
import { attemptScope, readAttempt, saveAttempt } from '../services/checkoutAttempt';
import { checkoutPayload, seatIdsForCommand } from '../services/chatBooking';
import { formatCurrency, formatDate, formatTime } from '../utils/formatters';

const errorText = (error, fallback) => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : fallback;
const orderScope = (userId, showtimeId, reservationId) => `ai:${attemptScope(userId, showtimeId, reservationId, [])}`;
const formatAmount = value => formatCurrency(value, 2);

export default function ChatBooking({ draft, userId, onReservation, onDiscard }) {
  const navigate = useNavigate();
  const { showtimeId } = draft;
  const [show, setShow] = useState(null);
  const [seats, setSeats] = useState(null);
  const [selected, setSelected] = useState([]);
  const [items, setItems] = useState(null);
  const [quantities, setQuantities] = useState({});
  const [skipFood, setSkipFood] = useState(false);
  const [pending, setPending] = useState(() => draft.reservationId && readAttempt(sessionStorage, orderScope(userId, showtimeId, draft.reservationId)));
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [menuError, setMenuError] = useState(false);
  const [error, setError] = useState('');
  const [checkoutConflict, setCheckoutConflict] = useState(false);
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());
  const operation = useRef(false);
  const mounted = useRef(false);
  const consumedCommand = useRef(null);
  const held = (seats || []).filter(seat => seat.status === 'HOLD' && seat.is_held_by_me);
  const reservation = held[0]?.reservation_id;
  const seconds = held.length ? Math.max(0, Math.ceil((Math.min(...held.map(seat => Date.parse(seat.hold_expired_at))) - now) / 1000)) : 0;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api.get(`/showtimes/${showtimeId}`, { signal: controller.signal, timeout: 5000 }),
      api.get(`/seats/showtime/${showtimeId}`, { signal: controller.signal, timeout: 5000 }),
    ]).then(([info, inventory]) => {
      if (controller.signal.aborted) return;
      setShow(info.data);
      setSeats(inventory.data);
      setLoadError(false);
      setNow(Date.now());
    }).catch(() => { if (!controller.signal.aborted) setLoadError(true); });
    return () => controller.abort();
  }, [showtimeId, revision]);

  useEffect(() => {
    if (!reservation || pending) return;
    const controller = new AbortController();
    api.get('/food-items', { signal: controller.signal, timeout: 5000 }).then(({ data }) => {
      if (controller.signal.aborted) return;
      setItems(data);
      setQuantities(current => Object.fromEntries(Object.entries(current).filter(([id]) => data.some(item => item.id === Number(id)))));
      setMenuError(false);
    }).catch(() => { if (!controller.signal.aborted) setMenuError(true); });
    return () => controller.abort();
  }, [reservation, pending, revision]);

  useEffect(() => {
    if (!reservation) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [reservation]);

  useEffect(() => {
    if (!draft.command || !seats || busy || consumedCommand.current === draft.command) return;
    consumedCommand.current = draft.command;
    if (reservation || pending) {
      setError('Hãy chọn Đổi ghế trước khi nhập nhóm ghế mới.');
      return;
    }
    try {
      setSelected(seatIdsForCommand(draft.command, seats));
      setError('');
    } catch (exception) {
      setError(exception.message);
    }
  }, [draft.command, seats, busy, reservation, pending]);

  function refresh() {
    setLoadError(false);
    setMenuError(false);
    setSelected([]);
    setSeats(null);
    setItems(null);
    setRevision(value => value + 1);
  }

  function startOperation() {
    if (operation.current || getCurrentUser()?.id !== userId) return false;
    operation.current = true;
    setBusy(true);
    setError('');
    return true;
  }

  function finishOperation() {
    operation.current = false;
    if (mounted.current) setBusy(false);
  }

  async function hold() {
    if (reservation || pending || !selected.length || !startOperation()) return;
    try {
      const { data } = await api.post('/ai/booking/hold', { showtime_id: showtimeId, seat_ids: selected }, { timeout: 9000 });
      if (!mounted.current) return;
      onReservation(data[0].reservation_id);
      refresh();
    } catch (exception) {
      if (!mounted.current) return;
      setError(errorText(exception, 'Chưa xác minh được ghế. Hãy kiểm tra danh sách mới.'));
      refresh();
    } finally { finishOperation(); }
  }

  async function release(discard = false) {
    if (!reservation || pending || !startOperation()) return;
    try {
      await api.post('/ai/booking/release', {
        showtime_id: showtimeId, reservation_id: reservation, seat_ids: held.map(seat => seat.seat_id),
      }, { timeout: 9000 });
      if (!mounted.current) return;
      if (discard) onDiscard();
      else {
        onReservation(null);
        setQuantities({});
        setSkipFood(false);
        refresh();
      }
    } catch (exception) {
      if (!mounted.current) return;
      setError(errorText(exception, 'Chưa xác minh được việc trả ghế.'));
      refresh();
    } finally { finishOperation(); }
  }

  let preview = null;
  if (reservation && seconds > 0 && (skipFood || items)) {
    try { preview = checkoutPayload(showtimeId, reservation, held, skipFood ? [] : items, quantities); }
    catch { /* A missing or invalid price keeps checkout unavailable. */ }
  }

  async function checkout() {
    if ((!pending && !preview) || !startOperation()) return;
    setCheckoutConflict(false);
    const scope = orderScope(userId, showtimeId, pending?.payload.reservation_id || reservation);
    let attempt = pending;
    try {
      if (!attempt) {
        onReservation(reservation);
        attempt = saveAttempt(sessionStorage, scope, preview, crypto.randomUUID());
      }
      setPending(attempt);
      const { data } = await api.post('/ai/booking/checkout', attempt.payload, {
        headers: { 'Idempotency-Key': attempt.key }, timeout: 18000,
      });
      if (!mounted.current || getCurrentUser()?.id !== userId) return;
      sessionStorage.removeItem(scope);
      onDiscard();
      navigate(`/payment/${data.bookingId}`);
    } catch (exception) {
      if (!mounted.current) return;
      setError(errorText(exception, 'Chưa nhận được kết quả tạo đơn. Hãy thử lại yêu cầu này.'));
      if ([400, 404, 409, 422].includes(exception.response?.status)) {
        setCheckoutConflict(exception.response.status === 409);
        sessionStorage.removeItem(scope);
        setPending(null);
        refresh();
      }
    } finally { finishOperation(); }
  }

  return <section className="assistant-booking" aria-label="Đặt vé trong chat">
    <h3>{show?.film_title || 'Đặt vé trong chat'}</h3>
    {show && <p>{[show.theater_name, show.room_name, formatDate(show.show_date), formatTime(show.start_time)].filter(Boolean).join(' · ')}</p>}
    {error && <p className="assistant-error" role="alert">{error}</p>}
    {checkoutConflict && <Link className="assistant-direct-link" to="/user-info">Xem đơn của tôi</Link>}
    {pending ? <>
      <p role="status">Đang xác minh yêu cầu tạo đơn trước đó. Tổng đã xác nhận {formatAmount(pending.payload.total_amount)}.</p>
      <button type="button" className="assistant-primary" disabled={busy} onClick={checkout}>Thử lại tạo đơn</button>
    </> : loadError ? <>
      <p role="alert">Chưa tải được suất và ghế.</p>
      <button type="button" className="assistant-direct-link" onClick={refresh}>Tải lại</button>
      <button type="button" className="assistant-direct-link" onClick={onDiscard}>Đóng bước đặt vé</button>
    </> : !seats ? <p role="status">Đang tải ghế…</p> : reservation ? <>
      <p>Ghế đang giữ {held.map(seat => seat.seat_name).join(', ')} · Tiền vé {formatAmount(held.reduce((total, seat) => total + Number(seat.price), 0))}</p>
      {seconds > 0 ? <p>Còn {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')} giữ ghế</p> : <p role="status">Ghế đã hết hạn. Hãy cập nhật để chọn lại.</p>}
      {seconds > 0 && <>
        <h4>Bỏng, nước và combo</h4>
        {menuError ? <><p role="alert">Chưa tải được thực đơn. Bạn có thể tải lại hoặc bỏ qua.</p>
          <button type="button" className="assistant-direct-link" onClick={refresh}>Tải lại thực đơn</button>
        </> : !items && <p role="status">Đang tải thực đơn…</p>}
        {!skipFood && items?.map(item => <div className="assistant-booking-food" key={item.id}>
          <span>{item.name} · {formatAmount(item.price)}</span>
          <div className="assistant-booking-actions">
            <button type="button" className="assistant-direct-link" aria-label={`Bớt ${item.name}`} disabled={busy || !quantities[item.id]}
              onClick={() => setQuantities(old => ({ ...old, [item.id]: old[item.id] - 1 }))}>−</button>
            <span>{quantities[item.id] || 0}</span>
            <button type="button" className="assistant-direct-link" aria-label={`Thêm ${item.name}`} disabled={busy || quantities[item.id] >= 20}
              onClick={() => setQuantities(old => ({ ...old, [item.id]: (old[item.id] || 0) + 1 }))}>+</button>
          </div>
        </div>)}
        <button type="button" className="assistant-direct-link" disabled={busy}
          onClick={() => { setSkipFood(value => !value); setQuantities({}); }}>{skipFood ? 'Chọn lại đồ ăn' : 'Bỏ qua đồ ăn'}</button>
        {preview && <p><span>Tiền món {formatAmount(Number(preview.total_amount) - preview.seats.reduce((total, seat) => total + Number(seat.price), 0))}</span> · <strong>Tổng {formatAmount(preview.total_amount)}</strong></p>}
      </>}
      <div className="assistant-booking-actions">
        {seconds > 0 && <button type="button" className="assistant-primary" onClick={checkout} disabled={busy || !preview}>Xác nhận đặt vé</button>}
        <button type="button" className="assistant-direct-link" onClick={() => seconds > 0 ? release() : refresh()} disabled={busy}>{seconds > 0 ? 'Đổi ghế' : 'Cập nhật ghế'}</button>
        <button type="button" className="assistant-direct-link" onClick={() => release(true)} disabled={busy}>Hủy giữ ghế</button>
        <button type="button" className="assistant-direct-link" onClick={onDiscard} disabled={busy}>Đóng bước đặt vé</button>
      </div>
    </> : <>
      <p>Đã chọn {selected.length} ghế{draft.partySize ? ` · yêu cầu ban đầu ${draft.partySize} vé` : ''}. Bạn có thể gõ “ghế A5 A6”.</p>
      <div className="assistant-booking-seats" role="group" aria-label="Ghế của suất chiếu">
        {seats.map(seat => <button type="button" key={seat.seat_id} className="assistant-direct-link"
          aria-label={`Ghế ${seat.seat_name}, ${seat.status === 'AVAILABLE' ? formatAmount(seat.price) : 'không khả dụng'}`}
          aria-pressed={selected.includes(seat.seat_id)} disabled={busy || seat.status !== 'AVAILABLE' || (selected.length === 20 && !selected.includes(seat.seat_id))}
          onClick={() => setSelected(old => old.includes(seat.seat_id) ? old.filter(id => id !== seat.seat_id) : [...old, seat.seat_id])}>{seat.seat_name}</button>)}
      </div>
      <div className="assistant-booking-actions">
        <button type="button" className="assistant-primary" onClick={hold} disabled={busy || !selected.length}>Giữ ghế</button>
        <button type="button" className="assistant-direct-link" onClick={onDiscard} disabled={busy}>Đóng bước đặt vé</button>
      </div>
    </>}
  </section>;
}
