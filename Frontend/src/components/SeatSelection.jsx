import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowRight, RefreshCw } from "lucide-react";
import api from "../config/api";
import { clearSession, getCurrentUser } from "../services/authStorage";
import { formatCurrency, formatDate, formatTime } from "../utils/formatters";
import { BookingSteps, Button, PageState, Poster } from "./ui/Primitives";

const typeLabel = (type) =>
  ({
    vip: "VIP",
    premium: "VIP",
    couple: "Đôi",
    standard: "Thường",
    normal: "Thường",
  })[type?.toLowerCase()] ||
  type ||
  "Chưa cập nhật";
export default function SeatSelection() {
  const { showtimeId } = useParams();
  const navigate = useNavigate();
  const [showtimeInfo, setShowtimeInfo] = useState(null);
  const [seatData, setSeatData] = useState([]);
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notification, setNotification] = useState("");
  const [syncError, setSyncError] = useState(false);
  const [busySeat, setBusySeat] = useState(null);
  const [bookingBusy, setBookingBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const operation = useRef(false);
  const applySeats = useCallback((seats) => {
    setSeatData(seats);
    setSelectedSeats(
      seats
        .filter((s) => s.is_held_by_me && s.status === "HOLD")
        .map((s) => s.seat_id),
    );
    setSyncError(false);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setSelectedSeats([]);
    Promise.all([
      api.get(`/showtimes/${showtimeId}`, { signal: controller.signal }),
      api.get(`/seats/showtime/${showtimeId}`, { signal: controller.signal }),
    ])
      .then(([showtime, seats]) => {
        setShowtimeInfo(showtime.data);
        applySeats(seats.data);
      })
      .catch((e) => {
        if (e.code !== "ERR_CANCELED")
          setError("Không thể tải thông tin suất chiếu và ghế.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [showtimeId, attempt, applySeats]);
  const refreshSeats = useCallback(async () => {
    if (operation.current) return;
    operation.current = true;
    try {
      const r = await api.get(`/seats/showtime/${showtimeId}`);
      applySeats(r.data);
    } catch {
      setSyncError(true);
    } finally {
      operation.current = false;
    }
  }, [showtimeId, applySeats]);
  useEffect(() => {
    if (loading || error) return;
    const timer = setInterval(refreshSeats, 15000);
    return () => clearInterval(timer);
  }, [refreshSeats, loading, error]);
  const requireUser = () => {
    const user = getCurrentUser();
    if (!user?.id || !user.access_token) {
      navigate("/loginpage", {
        state: {
          redirectTo: `/seat-selection/${showtimeId}`,
          message: "Vui lòng đăng nhập để đặt vé",
        },
      });
      return null;
    }
    return user;
  };
  const handleSeatClick = async (seat) => {
    const isSelected = selectedSeats.includes(seat.seat_id);
    if (
      operation.current ||
      (seat.status !== "AVAILABLE" && !isSelected) ||
      !requireUser()
    )
      return;
    operation.current = true;
    setBusySeat(seat.seat_id);
    setNotification("");
    try {
      if (isSelected) {
        await api.post("/seats/release", {
          showtime_id: parseInt(showtimeId),
          seat_ids: [seat.seat_id],
        });
        setSelectedSeats((prev) => prev.filter((id) => id !== seat.seat_id));
        setSeatData((prev) =>
          prev.map((s) =>
            s.seat_id === seat.seat_id
              ? {
                  ...s,
                  status: "AVAILABLE",
                  is_held_by_me: false,
                  hold_expired_at: null,
                }
              : s,
          ),
        );
      } else {
        const response = await api.post("/seats/hold", {
          showtime_id: parseInt(showtimeId),
          seat_ids: [seat.seat_id],
        });
        const hold = response.data?.[0];
        setSelectedSeats((prev) => [...new Set([...prev, seat.seat_id])]);
        setSeatData((prev) =>
          prev.map((s) =>
            s.seat_id === seat.seat_id
              ? {
                  ...s,
                  status: "HOLD",
                  is_held_by_me: true,
                  hold_expired_at: hold?.hold_expired_at || s.hold_expired_at,
                }
              : s,
          ),
        );
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setNotification(
        typeof detail === "string"
          ? detail
          : "Không thể giữ hoặc hủy ghế. Vui lòng thử lại.",
      );
      try {
        const r = await api.get(`/seats/showtime/${showtimeId}`);
        applySeats(r.data);
      } catch {
        setSyncError(true);
      }
    } finally {
      operation.current = false;
      setBusySeat(null);
    }
  };
  const chosen = selectedSeats
    .map((id) => seatData.find((s) => s.seat_id === id))
    .filter(Boolean);
  const total = chosen.reduce(
    (sum, seat) => sum + (seat.price == null ? NaN : Number(seat.price)),
    0,
  );
  const handleBooking = async () => {
    if (
      operation.current ||
      !selectedSeats.length ||
      syncError ||
      !Number.isFinite(total)
    )
      return;
    const user = requireUser();
    if (!user) return;
    operation.current = true;
    setBookingBusy(true);
    setNotification("");
    try {
      const response = await api.post("/bookings", {
        userId: user.id,
        showtimeId: parseInt(showtimeId),
        totalAmount: total,
        paymentMethod: "Online",
        seats: chosen.map((s) => ({ seat_id: s.seat_id, price: s.price })),
      });
      navigate(`/payment/${response.data.bookingId}`);
    } catch (err) {
      if (err.response?.status === 401) {
        clearSession();
        navigate("/loginpage", {
          state: {
            redirectTo: `/seat-selection/${showtimeId}`,
            message: "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.",
          },
        });
      } else {
        setNotification(
          typeof err.response?.data?.detail === "string"
            ? err.response.data.detail
            : "Không thể tạo đơn vé. Vui lòng thử lại.",
        );
        try {
          const r = await api.get(`/seats/showtime/${showtimeId}`);
          applySeats(r.data);
        } catch {
          setSyncError(true);
        }
      }
    } finally {
      operation.current = false;
      setBookingBusy(false);
    }
  };
  if (loading) return <PageState loading title="Đang tải sơ đồ ghế…" />;
  if (error)
    return (
      <PageState
        title="Chưa tải được sơ đồ ghế"
        message={error}
        onRetry={() => setAttempt((v) => v + 1)}
      />
    );
  const rows = [
    ...new Set(
      seatData.map((s) => s.seat_name?.match(/^[^0-9]+/)?.[0]).filter(Boolean),
    ),
  ].sort();
  return (
    <div className="shell page-section">
      <BookingSteps current={1} />
      <p className="eyebrow">Chỗ ngồi cho trải nghiệm của bạn</p>
      <h1 className="page-title">Chọn ghế</h1>
      {notification && (
        <div
          className="flex justify-between items-center gap-3 border border-red-200 bg-red-50 text-red-800 rounded-xl p-4 mb-5"
          role="alert"
        >
          <span>{notification}</span>
          <Button
            variant="ghost"
            aria-label="Đóng thông báo"
            onClick={() => setNotification("")}
          >
            ×
          </Button>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px] items-start">
        <div className="min-w-0">
          {showtimeInfo && (
            <section className="surface flex gap-4 mb-6">
              <Poster
                src={showtimeInfo.image}
                title={showtimeInfo.film_title}
                className="!w-20 h-30 rounded-lg shrink-0"
              />
              <div className="min-w-0">
                <h2 className="text-xl font-bold mb-2">
                  {showtimeInfo.film_title}
                </h2>
                <p className="text-sm text-gray-600 mb-2">
                  {showtimeInfo.theater_name} · {showtimeInfo.room_name}
                </p>
                <p className="text-sm font-semibold">
                  {formatDate(showtimeInfo.show_date)} ·{" "}
                  {formatTime(showtimeInfo.start_time)}
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  {[showtimeInfo.format, showtimeInfo.duration]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
            </section>
          )}
          <section className="surface">
            <div className="section-heading mb-3">
              <h2 className="!text-lg">Sơ đồ ghế</h2>
              <Button
                variant="ghost"
                onClick={refreshSeats}
                disabled={busySeat !== null || bookingBusy}
              >
                <RefreshCw size={16} />
                Cập nhật
              </Button>
            </div>
            <p className="text-xs text-gray-500 mb-6">
              Chọn ghế để giữ chỗ. Chọn lại để hủy giữ. Vuốt ngang trong sơ đồ
              nếu cần.
            </p>
            {syncError && (
              <div
                role="alert"
                className="text-sm text-red-700 bg-red-50 p-3 rounded-lg mb-4"
              >
                Chưa cập nhật được trạng thái ghế. Hãy nhấn “Cập nhật” trước khi
                tiếp tục.
              </div>
            )}
            <div className="screen">Màn hình</div>
            {!seatData.length ? (
              <PageState title="Chưa có sơ đồ ghế cho suất chiếu này" />
            ) : (
              <div
                className="seat-scroll"
                role="region"
                aria-label="Sơ đồ ghế có thể cuộn ngang"
                tabIndex={0}
              >
                <div className="seat-map">
                  {rows.map((row) => (
                    <div key={row} className="flex gap-2 items-center">
                      <span
                        className="w-6 text-sm font-bold shrink-0"
                        aria-hidden="true"
                      >
                        {row}
                      </span>
                      {seatData
                        .filter(
                          (s) =>
                            s.seat_name?.startsWith(row) &&
                            s.seat_name.match(/^[^0-9]+/)?.[0] === row,
                        )
                        .sort(
                          (a, b) =>
                            parseInt(a.seat_name.replace(row, "")) -
                            parseInt(b.seat_name.replace(row, "")),
                        )
                        .map((seat) => {
                          const selected = selectedSeats.includes(seat.seat_id);
                          const booked = seat.status === "BOOKED";
                          const held = seat.status === "HOLD" && !selected;
                          const type = seat.seat_type?.toLowerCase();
                          const state = booked
                            ? "Đã đặt"
                            : selected
                              ? "Đang chọn"
                              : held
                                ? "Đang giữ"
                                : seat.status === "AVAILABLE"
                                  ? "Trống"
                                  : "Không khả dụng";
                          const style = booked
                            ? "seat-booked"
                            : selected
                              ? "seat-selected"
                              : held
                                ? "seat-held"
                                : ["vip", "premium"].includes(type)
                                  ? "seat-vip"
                                  : type === "couple"
                                    ? "seat-couple"
                                    : "seat-standard";
                          return (
                            <button
                              key={seat.seat_id}
                              className={`seat ${style}`}
                              aria-pressed={selected}
                              aria-busy={busySeat === seat.seat_id || undefined}
                              aria-label={`Ghế ${seat.seat_name}, ${typeLabel(seat.seat_type)}, ${formatCurrency(seat.price)}, ${state}`}
                              title={`${typeLabel(seat.seat_type)} · ${formatCurrency(seat.price)} · ${state}`}
                              disabled={
                                booked ||
                                held ||
                                (!selected && seat.status !== "AVAILABLE") ||
                                busySeat !== null ||
                                bookingBusy
                              }
                              onClick={() => handleSeatClick(seat)}
                            >
                              {busySeat === seat.seat_id ? "…" : seat.seat_name}
                            </button>
                          );
                        })}
                      <span
                        className="w-6 text-sm font-bold shrink-0"
                        aria-hidden="true"
                      >
                        {row}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex flex-wrap justify-center gap-x-5 gap-y-3 mt-6">
              {[
                ["seat-standard", "Trống / Thường"],
                ["seat-vip", "Trống / VIP"],
                ["seat-couple", "Trống / Đôi"],
                ["seat-selected", "Đang chọn"],
                ["seat-held", "Đang giữ"],
                ["seat-booked", "Đã đặt"],
              ].map(([style, label]) => (
                <div className="flex items-center gap-2 text-xs" key={label}>
                  <span
                    className={`seat ${style} !w-4 !h-4`}
                    aria-hidden="true"
                  />
                  {label}
                </div>
              ))}
            </div>
          </section>
        </div>
        <aside className="surface booking-summary">
          <h2 className="text-xl font-bold mb-5">Thông tin đặt vé</h2>
          <div className="space-y-4" aria-live="polite">
            {chosen.length ? (
              chosen.map((seat) => (
                <div key={seat.seat_id}>
                  <div className="flex gap-2 justify-between text-sm">
                    <span className="font-semibold">
                      {seat.seat_name} · {typeLabel(seat.seat_type)}
                    </span>
                    <span>{formatCurrency(seat.price)}</span>
                  </div>
                  {seat.hold_expired_at && (
                    <p className="text-xs text-gray-500 mt-1">
                      Giữ đến {formatTime(seat.hold_expired_at)} ·{" "}
                      {formatDate(seat.hold_expired_at)}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p className="text-sm text-gray-500">
                Chưa chọn ghế. Chọn một ghế trống trên sơ đồ.
              </p>
            )}
          </div>
          <div className="border-t border-gray-200 mt-5 pt-5 flex justify-between gap-3">
            <span className="font-semibold">Tổng tiền</span>
            <span className="text-xl font-bold text-red-700">
              {formatCurrency(total)}
            </span>
          </div>
          <Button
            className="w-full mt-6"
            disabled={
              !chosen.length ||
              busySeat !== null ||
              syncError ||
              !Number.isFinite(total)
            }
            busy={bookingBusy}
            onClick={handleBooking}
          >
            {bookingBusy ? "Đang tạo đơn vé…" : "Tiếp tục thanh toán"}
            <ArrowRight size={17} />
          </Button>
          <Button
            className="w-full mt-2"
            variant="ghost"
            onClick={() => navigate(-1)}
          >
            Quay lại lịch chiếu
          </Button>
        </aside>
      </div>
    </div>
  );
}
