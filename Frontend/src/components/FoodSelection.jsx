import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CupSoda, Minus, Plus, Popcorn } from "lucide-react";
import api from "../config/api";
import { clearSession, getCurrentUser } from "../services/authStorage";
import { formatCurrency, formatTime } from "../utils/formatters";
import { BookingSteps, Button, PageState } from "./ui/Primitives";

const categories = [["COMBO", "Combo"], ["POPCORN", "Bỏng"], ["DRINK", "Nước"]];
const errorText = (error, fallback) => typeof error.response?.data?.detail === "string"
  ? error.response.data.detail : fallback;

export default function FoodSelection() {
  const { showtimeId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const seatIds = useRef(location.state?.selectedSeatIds);
  const submitting = useRef(false);
  const [seats, setSeats] = useState([]);
  const [items, setItems] = useState([]);
  const [quantities, setQuantities] = useState({});
  const [category, setCategory] = useState("COMBO");
  const [loading, setLoading] = useState(true);
  const [menuLoading, setMenuLoading] = useState(true);
  const [seatError, setSeatError] = useState("");
  const [menuError, setMenuError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const user = getCurrentUser();
    if (!user?.id || !user.access_token) {
      navigate("/loginpage", { state: { redirectTo: `/seat-selection/${showtimeId}` } });
      return;
    }
    const controller = new AbortController();
    let refreshing = false;
    setLoading(true);
    const refresh = async () => {
      if (refreshing || submitting.current) return;
      refreshing = true;
      try {
        const r = await api.get(`/seats/showtime/${showtimeId}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!seatIds.current) seatIds.current = r.data.filter(s => s.is_held_by_me).map(s => s.seat_id);
        setSeats(r.data.filter(s => seatIds.current.includes(s.seat_id)));
        setSeatError("");
      } catch (e) {
        if (e.code !== "ERR_CANCELED") setSeatError("Chưa xác minh được ghế đang giữ. Vui lòng thử lại.");
      } finally {
        refreshing = false;
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    refresh();
    const poll = setInterval(refresh, 15000);
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => { controller.abort(); clearInterval(poll); clearInterval(clock); };
  }, [showtimeId, navigate, attempt]);

  useEffect(() => {
    const controller = new AbortController();
    setMenuLoading(true);
    setMenuError("");
    api.get("/food-items", { signal: controller.signal }).then(r => {
      if (controller.signal.aborted) return;
      setItems(r.data);
      setQuantities(previous => Object.fromEntries(Object.entries(previous)
        .filter(([id]) => r.data.some(item => item.id === Number(id)))));
    }).catch(e => {
      if (e.code !== "ERR_CANCELED") setMenuError("Chưa tải được thực đơn. Bạn có thể thử lại hoặc chỉ mua vé.");
    }).finally(() => { if (!controller.signal.aborted) setMenuLoading(false); });
    return () => controller.abort();
  }, [attempt]);

  const validSeats = seats.length > 0 && seats.length === seatIds.current?.length
    && seats.every(s => s.status === "HOLD" && s.is_held_by_me
      && new Date(s.hold_expired_at).getTime() > now && Number.isFinite(Number(s.price)));
  const deadline = Math.min(...seats.map(s => new Date(s.hold_expired_at).getTime()));
  const seconds = Math.max(0, Math.floor((deadline - now) / 1000));
  const ticketTotal = seats.reduce((sum, seat) => sum + Number(seat.price), 0);
  const selected = items.filter(item => quantities[item.id] > 0);
  const foodTotal = selected.reduce((sum, item) => sum + Number(item.price) * quantities[item.id], 0);
  const change = (id, delta) => setQuantities(previous => ({ ...previous,
    [id]: Math.min(20, Math.max(0, (previous[id] || 0) + delta)) }));

  async function checkout(skipFood = false) {
    if (submitting.current || !validSeats || seatError || (!skipFood && (menuError || menuLoading))) return;
    const user = getCurrentUser();
    if (!user?.id || !user.access_token) {
      navigate("/loginpage", { state: { redirectTo: `/seat-selection/${showtimeId}` } });
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const r = await api.post("/bookings", {
        userId: user.id, showtimeId: Number(showtimeId), paymentMethod: "Online",
        totalAmount: ticketTotal + (skipFood ? 0 : foodTotal),
        seats: seats.map(s => ({ seat_id: s.seat_id, price: Number(s.price) })),
        foodItems: skipFood ? [] : selected.map(item => ({ food_item_id: item.id, quantity: quantities[item.id] })),
      });
      navigate(`/payment/${r.data.bookingId}`, { replace: true });
    } catch (e) {
      if (e.response?.status === 401) {
        clearSession();
        navigate("/loginpage", { state: { redirectTo: `/seat-selection/${showtimeId}` } });
      } else {
        setError(errorText(e, "Không thể tạo đơn. Vui lòng thử lại."));
        setAttempt(v => v + 1);
      }
    } finally { submitting.current = false; setBusy(false); }
  }

  if (loading) return <PageState loading title="Đang kiểm tra ghế của bạn…" />;
  return <div className="shell page-section">
    <BookingSteps current={2} />
    <p className="eyebrow">Thêm hương vị cho buổi xem phim</p>
    <h1 className="page-title">Bỏng, nước & combo</h1>
    <p className="text-gray-600 mb-6">Chọn món lẻ hoặc combo yêu thích. Bạn có thể bỏ qua bước này.</p>
    {error && <p role="alert" className="bg-red-50 text-red-800 p-4 rounded-xl mb-5">{error}</p>}
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px] items-start">
      <section className="min-w-0">
        <div className="flex gap-2 mb-5" role="group" aria-label="Loại đồ ăn">
          {categories.map(([value, label]) => <Button key={value} variant={category === value ? "primary" : "secondary"}
            aria-pressed={category === value} onClick={() => setCategory(value)}>{label}</Button>)}
        </div>
        {menuLoading ? <PageState loading title="Đang tải thực đơn…" /> : menuError ?
          <PageState title="Chưa tải được thực đơn" message={menuError} onRetry={() => setAttempt(v => v + 1)} /> :
          <div className="grid gap-4 sm:grid-cols-2">
            {items.filter(item => item.category === category).map(item => <article className="surface flex flex-col" key={item.id}>
              <div className="bg-red-50 text-red-700 rounded-xl p-5 mb-4 flex justify-center" aria-hidden="true">
                {item.category === "DRINK" ? <CupSoda size={42} /> : <Popcorn size={42} />}
              </div>
              <h2 className="text-lg font-bold mb-2">{item.name}</h2>
              <p className="text-sm text-gray-600 mb-3">{item.description}</p>
              {item.components?.length > 0 && <ul className="text-sm text-gray-600 mb-4">
                {item.components.map(part => <li key={part.food_item_id}>{part.quantity} × {part.name}</li>)}
              </ul>}
              <div className="flex justify-between items-center gap-2 mt-auto">
                <strong className="text-red-700">{formatCurrency(item.price)}</strong>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" aria-label={`Giảm ${item.name}`} disabled={busy || !quantities[item.id]}
                    onClick={() => change(item.id, -1)}><Minus size={16} /></Button>
                  <output className="w-5 text-center" aria-label={`Số lượng ${item.name}`} aria-live="polite">{quantities[item.id] || 0}</output>
                  <Button variant="secondary" aria-label={`Thêm ${item.name}`} disabled={busy || quantities[item.id] >= 20 || !validSeats}
                    onClick={() => change(item.id, 1)}><Plus size={16} /></Button>
                </div>
              </div>
            </article>)}
            {!items.some(item => item.category === category) && <PageState title="Chưa có món đang bán trong nhóm này" />}
          </div>}
      </section>
      <aside className="surface booking-summary">
        <h2 className="text-xl font-bold mb-4">Đơn của bạn</h2>
        <p className="text-sm mb-3">Ghế: {seats.map(s => s.seat_name).join(", ") || "Chưa chọn"}</p>
        {validSeats && <p role="timer" className="text-sm bg-amber-50 text-amber-900 rounded-lg p-3 mb-4">
          Còn {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")} giữ ghế · đến {formatTime(seats.find(s => new Date(s.hold_expired_at).getTime() === deadline)?.hold_expired_at)}
        </p>}
        {seatError ? <PageState title="Chưa xác minh được ghế" message={seatError} onRetry={() => setAttempt(v => v + 1)} /> :
          !validSeats && <p role="alert" className="text-sm text-red-700 mb-4">Ghế đã hết hạn giữ hoặc không còn khả dụng. Vui lòng quay lại chọn ghế.</p>}
        <div className="space-y-3 text-sm mb-5" aria-live="polite">
          {selected.map(item => <div key={item.id} className="flex justify-between gap-3">
            <span>{quantities[item.id]} × {item.name}</span><span>{formatCurrency(Number(item.price) * quantities[item.id])}</span>
          </div>)}
          {!selected.length && <p className="text-gray-500">Chưa chọn bỏng, nước hoặc combo.</p>}
        </div>
        <dl className="border-t pt-4 space-y-3 text-sm">
          <div className="flex justify-between"><dt>Tiền vé</dt><dd>{formatCurrency(ticketTotal)}</dd></div>
          <div className="flex justify-between"><dt>Bỏng, nước & combo</dt><dd>{formatCurrency(foodTotal)}</dd></div>
          <div className="flex justify-between font-bold text-lg"><dt>Tổng cộng</dt><dd className="text-red-700">{formatCurrency(ticketTotal + foodTotal)}</dd></div>
        </dl>
        <Button className="w-full mt-5" busy={busy} disabled={!validSeats || !!seatError || !!menuError || menuLoading} onClick={() => checkout()}>
          Tiếp tục thanh toán <ArrowRight size={17} />
        </Button>
        <Button className="w-full mt-2" variant="secondary" disabled={busy || !validSeats || !!seatError} onClick={() => checkout(true)}>Bỏ qua, chỉ mua vé</Button>
        <Button className="w-full mt-2" variant="ghost" disabled={busy} onClick={() => navigate(`/seat-selection/${showtimeId}`)}><ArrowLeft size={16} /> Quay lại chọn ghế</Button>
      </aside>
    </div>
  </div>;
}
