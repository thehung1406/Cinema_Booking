import { useEffect, useState } from "react";
import { ArrowUpRight, MapPin } from "lucide-react";
import api from "../config/api";
import { Button, PageState } from "./ui/Primitives";

export default function CinemaList() {
  const [cinemas, setCinemas] = useState([]);
  const [selectedCity, setSelectedCity] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    api.get("/theaters/", { signal: controller.signal }).then(({ data }) => setCinemas(data)).catch(e => {
      if (e.code !== "ERR_CANCELED") setError("Không thể tải danh sách rạp. Vui lòng thử lại.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [attempt]);
  const filtered = selectedCity === "all" ? cinemas : cinemas.filter(c => c.city === selectedCity);
  return <div className="shell page-section">
    <p className="eyebrow">Hệ thống rạp</p><h1 className="page-title">Chọn rạp cho buổi xem</h1>
    <p className="text-gray-600 mb-8">Tìm rạp theo thành phố và chọn lịch chiếu phù hợp.</p>
    <div className="catalog-toolbar form-field mb-4"><label htmlFor="cinema-city">Thành phố</label><select id="cinema-city" value={selectedCity} onChange={e => setSelectedCity(e.target.value)} className="max-w-sm">
      <option value="all">Tất cả thành phố</option>{[...new Set(cinemas.map(c => c.city).filter(Boolean))].map(city => <option key={city}>{city}</option>)}
    </select></div>
    {loading ? <PageState loading title="Đang tải danh sách rạp…" /> : error ? <PageState title="Chưa tải được hệ thống rạp" message={error} onRetry={() => setAttempt(v => v + 1)} /> : !filtered.length ? <PageState title="Chưa có rạp phù hợp" message="Thử chọn thành phố khác." /> : <>
      <p role="status" className="text-sm text-gray-600">{filtered.length} rạp phù hợp</p>
      <div className="cinema-list">{filtered.map(cinema => <article className={`cinema-row ${!cinema.image ? "cinema-without-photo" : ""}`} key={cinema.id}>
        {cinema.image && <img className="cinema-photo" src={cinema.image} alt={cinema.name} loading="lazy" onError={e => { e.currentTarget.hidden = true; e.currentTarget.closest("article").classList.add("cinema-without-photo"); }} />}
        <div><p className="eyebrow">{cinema.city}</p><h2>{cinema.name}</h2><p className="flex items-start gap-2"><MapPin size={18} className="shrink-0 mt-1" aria-hidden="true" />{cinema.address || "Địa chỉ đang được cập nhật"}</p>{cinema.special && <p className="mt-3">{cinema.special}</p>}</div>
        <Button to={`/TicketBooking?theaterId=${cinema.id}`} variant="secondary">Chọn lịch tại rạp <ArrowUpRight size={18} /></Button>
      </article>)}</div>
    </>}
  </div>;
}
