import { useEffect, useState } from "react";
import { ArrowRight, CalendarDays, Film, MapPin } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../config/api";
import { formatDate, formatTime, localDateInput } from "../utils/formatters";
import { BookingSteps, Button, PageState } from "./ui/Primitives";

export default function TicketBooking() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialFilmId = params.get("filmId") || params.get("movieId") || "";
  const initialTheaterId =
    params.get("theaterId") || params.get("cinemaId") || "";
  const [movieId, setMovieId] = useState(initialFilmId);
  const [cinemaId, setCinemaId] = useState(initialTheaterId);
  const [date, setDate] = useState(localDateInput);
  const [movies, setMovies] = useState([]);
  const [cinemas, setCinemas] = useState([]);
  const [showtimes, setShowtimes] = useState([]);
  const [showtimeId, setShowtimeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [theatersLoading, setTheatersLoading] = useState(false);
  const [timesLoading, setTimesLoading] = useState(false);
  const [filmError, setFilmError] = useState("");
  const [theaterError, setTheaterError] = useState("");
  const [timesError, setTimesError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const retry = () => setAttempt((v) => v + 1);
  useEffect(() => {
    setMovieId(initialFilmId);
    setCinemaId(initialTheaterId);
    setShowtimeId(null);
  }, [initialFilmId, initialTheaterId]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setFilmError("");
    api
      .get("/films/", { signal: controller.signal })
      .then((r) => setMovies(r.data))
      .catch((e) => {
        if (e.code !== "ERR_CANCELED")
          setFilmError("Không thể tải danh sách phim.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    const controller = new AbortController();
    setCinemas([]);
    setTheaterError("");
    if (!movieId) {
      setTheatersLoading(false);
      return () => controller.abort();
    }
    setTheatersLoading(true);
    api
      .get(`/theaters/by-film/${movieId}`, { signal: controller.signal })
      .then((r) => {
        const list = Array.isArray(r.data)
          ? r.data
          : r.data.theaters || r.data.data || [r.data];
        setCinemas(list);
        setCinemaId((current) =>
          list.some((t) => String(t.id || t.theater_id) === String(current))
            ? current
            : "",
        );
      })
      .catch((e) => {
        if (e.code !== "ERR_CANCELED")
          setTheaterError("Không thể tải danh sách rạp cho phim này.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setTheatersLoading(false);
      });
    return () => controller.abort();
  }, [movieId, attempt]);
  useEffect(() => {
    const controller = new AbortController();
    setShowtimes([]);
    setShowtimeId(null);
    setTimesError("");
    if (!movieId || !cinemaId || !date || theatersLoading) {
      setTimesLoading(false);
      return () => controller.abort();
    }
    setTimesLoading(true);
    api
      .get("/showtimes", {
        signal: controller.signal,
        params: {
          film_id: parseInt(movieId),
          theater_id: parseInt(cinemaId),
          date,
        },
      })
      .then((r) => setShowtimes(r.data))
      .catch((e) => {
        if (e.code !== "ERR_CANCELED")
          setTimesError("Không thể tải suất chiếu. Vui lòng thử lại.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setTimesLoading(false);
      });
    return () => controller.abort();
  }, [movieId, cinemaId, date, theatersLoading, attempt]);
  if (loading && !movies.length)
    return <PageState loading title="Đang tải lịch chiếu…" />;
  if (filmError)
    return (
      <PageState
        title="Chưa tải được phim"
        message={filmError}
        onRetry={retry}
      />
    );
  const movie = movies.find((m) => String(m.id) === String(movieId));
  const cinema = cinemas.find(
    (c) => String(c.id || c.theater_id) === String(cinemaId),
  );
  const time = showtimes.find((s) => (s.id || s.showtime_id) === showtimeId);
  return (
    <div className="shell page-section">
      <BookingSteps />
      <div className="text-center mb-8">
        <p className="eyebrow">Bắt đầu buổi xem phim</p>
        <h1 className="page-title">Chọn lịch chiếu</h1>
        <p className="text-gray-500">
          Chọn lần lượt phim, rạp, ngày và suất chiếu.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px] items-start">
        <section className="surface">
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="form-field">
              <label htmlFor="booking-film" className="flex items-center gap-2">
                <Film size={18} />
                1. Chọn phim
              </label>
              <select
                id="booking-film"
                value={movieId}
                onChange={(e) => {
                  setMovieId(e.target.value);
                  setCinemaId("");
                  setShowtimeId(null);
                }}
                disabled={loading}
              >
                <option value="">Chọn phim muốn xem</option>
                {movies.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.title}
                  </option>
                ))}
              </select>
              {!movies.length && (
                <p className="text-sm text-gray-500">Chưa có phim để đặt vé.</p>
              )}
            </div>
            <div className="form-field">
              <label
                htmlFor="booking-theater"
                className="flex items-center gap-2"
              >
                <MapPin size={18} />
                2. Chọn rạp
              </label>
              <select
                id="booking-theater"
                value={cinemaId}
                disabled={!movieId || theatersLoading}
                onChange={(e) => {
                  setCinemaId(e.target.value);
                  setShowtimeId(null);
                }}
              >
                <option value="">
                  {theatersLoading ? "Đang tải rạp…" : "Chọn rạp chiếu"}
                </option>
                {cinemas.map((c) => (
                  <option
                    key={c.id || c.theater_id}
                    value={c.id || c.theater_id}
                  >
                    {c.name || c.theater_name}
                  </option>
                ))}
              </select>
              {movieId &&
                !theatersLoading &&
                !theaterError &&
                !cinemas.length && (
                  <p className="text-sm text-gray-500">
                    Phim chưa có rạp chiếu khả dụng.
                  </p>
                )}
            </div>
            <div className="form-field">
              <label htmlFor="booking-date" className="flex items-center gap-2">
                <CalendarDays size={18} />
                3. Chọn ngày
              </label>
              <input
                id="booking-date"
                type="date"
                value={date}
                min={localDateInput()}
                disabled={!cinemaId || theatersLoading}
                onChange={(e) => {
                  setDate(e.target.value);
                  setShowtimeId(null);
                }}
              />
            </div>
          </div>
          {theaterError && (
            <PageState
              title="Chưa tải được rạp"
              message={theaterError}
              onRetry={retry}
            />
          )}
          <div className="border-t border-gray-200 mt-7 pt-6">
            <h2 className="text-lg font-bold mb-4">4. Chọn suất chiếu</h2>
            {timesLoading ? (
              <PageState loading title="Đang tìm suất chiếu…" />
            ) : timesError ? (
              <PageState
                title="Chưa tải được lịch chiếu"
                message={timesError}
                onRetry={retry}
              />
            ) : showtimes.length ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {showtimes.map((s) => {
                  const sid = s.id || s.showtime_id;
                  const start = formatTime(s.start_time);
                  const hasPassed =
                    new Date(`${date}T${start}:00+07:00`).getTime() <=
                    Date.now();
                  const unavailable =
                    !sid || start === "Chưa xác định" || hasPassed;
                  return (
                    <button
                      key={sid}
                      disabled={unavailable}
                      aria-pressed={showtimeId === sid}
                      className={`rounded-xl border p-4 text-center disabled:opacity-45 ${showtimeId === sid ? "bg-red-50 border-red-600 text-red-700" : "border-gray-200 hover:border-red-400"}`}
                      onClick={() => setShowtimeId(sid)}
                    >
                      <span className="block font-bold text-lg">{start}</span>
                      <span className="block text-xs mt-1">
                        {s.room_name ||
                          (s.room_id
                            ? `Phòng ${s.room_id}`
                            : "Chưa có tên phòng")}
                        {s.format ? ` · ${s.format}` : ""}
                      </span>
                      {hasPassed && (
                        <span className="block text-xs mt-1">Đã bắt đầu</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <PageState
                title={
                  movieId && cinemaId && date
                    ? "Chưa có suất chiếu trong ngày này"
                    : "Lịch chiếu sẽ xuất hiện tại đây"
                }
                message={
                  movieId && cinemaId
                    ? "Thử chọn ngày hoặc rạp khác."
                    : "Hãy chọn phim và rạp để tiếp tục."
                }
              />
            )}
          </div>
        </section>
        <aside className="surface booking-summary">
          <h2 className="text-lg font-bold mb-5">Lựa chọn của bạn</h2>
          <dl className="space-y-4 text-sm">
            {[
              ["Phim", movie?.title],
              ["Rạp", cinema?.name || cinema?.theater_name],
              ["Ngày", date ? formatDate(date) : "Chưa chọn"],
              ["Suất chiếu", time ? formatTime(time.start_time) : null],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-gray-500 mb-1">{label}</dt>
                <dd className="font-semibold">{value || "Chưa chọn"}</dd>
              </div>
            ))}
          </dl>
          <Button
            className="w-full mt-6"
            disabled={!showtimeId || timesLoading || theatersLoading}
            onClick={() => navigate(`/seat-selection/${showtimeId}`)}
          >
            Tiếp tục chọn ghế <ArrowRight size={17} />
          </Button>
          <Button
            variant="ghost"
            className="w-full mt-2"
            onClick={() => navigate(-1)}
          >
            Quay lại
          </Button>
        </aside>
      </div>
    </div>
  );
}
