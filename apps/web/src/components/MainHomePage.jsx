import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ChevronLeft, ChevronRight, Ticket } from "lucide-react";
import useFilms from "../hooks/useFilms";
import { classifyMovies } from "../utils/filmUtils";
import MovieCard from "./ui/MovieCard";
import { Button, PageState, Poster } from "./ui/Primitives";
import PositiveFilms from "./PositiveFilms";

export default function MainHomePage() {
  const { data: films, loading, error, retry } = useFilms();
  const [slide, setSlide] = useState(0);
  if (loading)
    return <PageState loading title="Đang tìm những bộ phim dành cho bạn…" />;
  if (error)
    return (
      <PageState
        title="Chưa tải được danh sách phim"
        message={error}
        onRetry={retry}
      />
    );
  const { nowShowing, upcoming } = classifyMovies(films);
  const featured = nowShowing.slice(0, 5);
  const movie = featured[slide % (featured.length || 1)];
  return (
    <>
      <section
        className="hero"
        aria-label="Phim nổi bật"
        aria-roledescription="carousel"
      >
        <div className="shell hero-content">
          <div>
            <p className="text-red-300 text-xs font-bold tracking-[.15em] uppercase">
              ĐIỆN ẢNH • CẢM XÚC • KẾT NỐI
            </p>
            <h1>{movie?.title || "Một bộ phim. Một trải nghiệm mới."}</h1>
            <p className="text-gray-300 max-w-xl leading-7">
              {movie
                ? [movie.genre, movie.duration].filter(Boolean).join(" · ")
                : "Khám phá danh sách phim và tìm lịch chiếu phù hợp với bạn."}
            </p>
            <div className="flex flex-wrap gap-3 mt-6">
              <Button
                to={movie ? `/TicketBooking?filmId=${movie.id}` : "/movie"}
              >
                <Ticket size={18} />
                {movie ? "Đặt vé ngay" : "Khám phá phim"}
              </Button>
              {movie && (
                <Link
                  to={`/MovieDetail/${movie.id}`}
                  className="btn border border-gray-600 text-white"
                >
                  Chi tiết phim <ArrowRight size={16} />
                </Link>
              )}
            </div>
            {featured.length > 1 && (
              <div
                className="hero-controls"
                aria-label="Điều khiển phim nổi bật"
              >
                <button
                  className="hero-control"
                  aria-label="Phim trước"
                  onClick={() =>
                    setSlide((slide + featured.length - 1) % featured.length)
                  }
                >
                  <ChevronLeft />
                </button>
                {featured.map((f, index) => (
                  <button
                    key={f.id}
                    className="hero-control"
                    aria-label={`Xem phim nổi bật ${index + 1}: ${f.title}`}
                    aria-pressed={slide === index}
                    onClick={() => setSlide(index)}
                  >
                    {index + 1}
                  </button>
                ))}
                <button
                  className="hero-control"
                  aria-label="Phim tiếp theo"
                  onClick={() => setSlide((slide + 1) % featured.length)}
                >
                  <ChevronRight />
                </button>
              </div>
            )}
          </div>
          <Poster src={movie?.image} title={movie?.title || "CGV Cinema"} />
        </div>
      </section>
      {[
        ["Phim đang chiếu", nowShowing],
        ["Phim sắp chiếu", upcoming],
      ].map(([title, movies], index) => (
        <section key={title} className="shell page-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">
                {index === 0 ? "Hôm nay xem gì?" : "Đón chờ trên màn ảnh"}
              </p>
              <h2 className="mt-2">{title}</h2>
            </div>
            <Button to="/movie" variant="ghost">
              Xem tất cả <ArrowRight size={16} />
            </Button>
          </div>
          {movies.length ? (
            <div className="movie-grid">
              {movies.slice(0, 8).map((f) => (
                <MovieCard movie={f} key={f.id} />
              ))}
            </div>
          ) : (
            <PageState
              title={`Chưa có ${title.toLowerCase()}`}
              message="Danh sách sẽ được cập nhật khi có thông tin phim."
            />
          )}
          {index === 0 && <PositiveFilms />}
        </section>
      ))}
      <section className="bg-white border-t border-gray-200">
        <div className="shell py-10 grid gap-6 sm:grid-cols-3">
          {[
            ["01", "Tìm lịch chiếu", "Chọn phim, rạp và thời gian phù hợp."],
            [
              "02",
              "Chọn ghế yêu thích",
              "Xem sơ đồ ghế và tổng tiền trước khi tiếp tục.",
            ],
            [
              "03",
              "Thanh toán & nhận vé",
              "Kiểm tra thông tin đơn vé và thanh toán qua VNPay.",
            ],
          ].map(([number, title, description]) => (
            <div key={number} className="flex gap-4">
              <span className="eyebrow mt-1">{number}</span>
              <div>
                <h2 className="font-bold mb-2">{title}</h2>
                <p className="text-sm text-gray-500 leading-6">{description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
