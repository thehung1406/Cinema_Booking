import { useState } from "react";
import { Search } from "lucide-react";
import useFilms from "../hooks/useFilms";
import { isNowShowing, isUpcoming } from "../utils/filmUtils";
import MovieCard from "./ui/MovieCard";
import { PageState } from "./ui/Primitives";

export default function Movie() {
  const { data: movies, loading, error, retry } = useFilms();
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const filtered = movies.filter(
    (movie) =>
      (filter === "all" ||
        (filter === "showing" ? isNowShowing(movie) : isUpcoming(movie))) &&
      (movie.title || "")
        .toLocaleLowerCase("vi")
        .includes(query.trim().toLocaleLowerCase("vi")),
  );
  return (
    <div className="shell page-section">
      <p className="eyebrow">Khám phá điện ảnh</p>
      <h1 className="page-title">Chọn phim cho buổi hẹn tiếp theo</h1>
      <p className="text-gray-500 mb-8">
        Xem thông tin phim và tìm lịch chiếu tại rạp bạn yêu thích.
      </p>
      <div className="surface flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div className="filter-buttons" aria-label="Lọc phim">
          {[
            ["all", "Tất cả"],
            ["showing", "Đang chiếu"],
            ["upcoming", "Sắp chiếu"],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="relative md:w-72">
          <Search
            size={18}
            className="absolute left-3 top-3.5 text-gray-400"
            aria-hidden="true"
          />
          <input
            aria-label="Tìm phim theo tên"
            type="search"
            className="w-full min-w-0 border border-gray-300 rounded-xl pl-10 pr-3 py-3 text-sm"
            placeholder="Tìm tên phim…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      {loading ? (
        <PageState loading title="Đang tải danh sách phim…" />
      ) : error ? (
        <PageState title="Chưa tải được phim" message={error} onRetry={retry} />
      ) : filtered.length ? (
        <>
          <p className="text-sm text-gray-500 mb-4" role="status">
            {filtered.length} phim phù hợp
          </p>
          <div className="movie-grid">
            {filtered.map((movie) => (
              <MovieCard key={movie.id} movie={movie} />
            ))}
          </div>
        </>
      ) : (
        <PageState
          title="Không tìm thấy phim phù hợp"
          message="Thử đổi tên phim hoặc chọn danh mục khác."
        />
      )}
    </div>
  );
}
