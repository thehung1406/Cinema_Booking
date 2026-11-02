import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../config/api";
import { Button, PageState, Poster } from "./ui/Primitives";

export default function PositiveFilms() {
  const [films, setFilms] = useState([]);
  const [theaters, setTheaters] = useState([]);
  const [theater, setTheater] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api
      .get("/theaters", { signal: controller.signal })
      .then((r) => setTheaters(r.data))
      .catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    api
      .get("/films/positive-trending", {
        signal: controller.signal,
        params: {
          theater_id: theater || undefined,
          show_date: date || undefined,
        },
      })
      .then((r) => {
        setFilms(r.data);
        setStatus("ready");
      })
      .catch((e) => {
        if (e.code !== "ERR_CANCELED") setStatus("error");
      });
    return () => controller.abort();
  }, [theater, date, attempt]);
  return (
    <section className="mt-12 pt-10 border-t border-gray-200">
      <h2 className="text-2xl font-bold mb-2">Phim được đánh giá tích cực</h2>
      <p className="text-gray-600 mb-4">
        Phản hồi cộng đồng trong 30 ngày, xếp hạng có tính đến số lượng đánh giá
        và còn suất chiếu.
      </p>
      <div className="flex flex-wrap gap-3 mb-5">
        <select
          aria-label="Lọc theo rạp"
          value={theater}
          onChange={(e) => setTheater(e.target.value)}
          className="border rounded p-2"
        >
          <option value="">Tất cả rạp</option>
          {theaters.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
        <input
          aria-label="Ngày xem"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="border rounded p-2"
        />
      </div>
      {status === "loading" && <PageState loading title="Đang tải phản hồi…" />}
      {status === "error" && (
        <PageState
          title="Chưa tải được phản hồi"
          message="Bạn vẫn có thể đặt vé tại danh sách phim."
          onRetry={() => setAttempt((v) => v + 1)}
        />
      )}
      {status === "ready" && !films.length && (
        <p className="bg-gray-50 border rounded-lg p-6">
          Chưa có phim đủ đánh giá hợp lệ và suất chiếu phù hợp.
        </p>
      )}
      {status === "ready" && (
        <div className="movie-grid">
          {films.map((f) => (
            <article key={f.film_id} className="movie-card">
              <Link
                to={`/movie/${f.film_id}`}
                aria-label={`Xem chi tiết ${f.title}`}
              >
                <Poster src={f.image} title={f.title} loading="lazy" />
              </Link>
              <div className="movie-card-body">
                <h3>
                  <Link to={`/movie/${f.film_id}`}>{f.title}</Link>
                </h3>
                <p className="!text-green-700">
                  {Math.round(f.summary.positive_ratio * 100)}% tích cực
                </p>
                <p>
                  {f.summary.total} đánh giá · {f.summary.window_days} ngày
                </p>
                <Button
                  className="w-full mt-auto"
                  to={`/TicketBooking?filmId=${f.film_id}`}
                >
                  Đặt vé
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
