import EditorialMoment from "./ui/EditorialMoment";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowUpRight, Ticket } from "lucide-react";
import useFilms from "../hooks/useFilms";
import { classifyMovies } from "../utils/filmUtils";
import MovieCard from "./ui/MovieCard";
import { Button, PageState, Poster } from "./ui/Primitives";
import PositiveFilms from "./PositiveFilms";

export default function MainHomePage() {
  const { data: films, loading, error, retry } = useFilms();
  if (loading) return <section className="home-state"><PageState loading title="Đang tìm những bộ phim dành cho bạn…" /></section>;
  if (error) return <section className="home-state"><PageState title="Chưa tải được danh sách phim" message={error} onRetry={retry} /></section>;
  const { nowShowing, upcoming } = classifyMovies(films);
  const movie = nowShowing[0] || upcoming[0];
  return <>
    <section className="hero editorial-hero" aria-label="Phim nổi bật" data-enter>
      <div className="shell hero-content">
        <div className="hero-copy">
          <p className="eyebrow"><span className="status-dot" /> Phim tại CGV</p>
          <h1>{movie?.title || "Phim & lịch chiếu tại CGV"}</h1>
          <p className="hero-lead">{movie ? [movie.genre, movie.duration].filter(Boolean).join(" · ") : "Xem danh sách phim và chọn lịch chiếu phù hợp với bạn."}</p>
          <div className="hero-actions">
            <Button to={movie ? `/TicketBooking?filmId=${movie.id}` : "/movie"}><Ticket size={18} aria-hidden="true" />{movie ? "Đặt vé ngay" : "Xem danh sách phim"}</Button>
            {movie && <Link to={`/MovieDetail/${movie.id}`} className="btn btn-secondary">Chi tiết phim <ArrowUpRight size={18} aria-hidden="true" /></Link>}
          </div>
          <div className="hero-note"><span>Phim. Rạp. Suất chiếu.</span><Link to="/ticket-booking">Chọn buổi xem của bạn <ArrowRight size={16} aria-hidden="true" /></Link></div>
        </div>
        <div className="hero-art"><Poster src={movie?.image} title={movie?.title || "CGV Cinema Booking"} fetchPriority="high" /></div>
      </div>
    </section>
    <section className="shell page-section home-programme">
      <div className="section-heading"><div><p className="eyebrow">Lịch phim</p><h2>Phim đang chiếu</h2></div><Button to="/movie?status=showing" variant="ghost">Xem tất cả <ArrowUpRight size={18} /></Button></div>
      {nowShowing.length ? <div className="movie-grid">{nowShowing.slice(0, 4).map(f => <MovieCard movie={f} key={f.id} />)}</div> : <PageState title="Chưa có phim đang chiếu" message="Danh sách sẽ được cập nhật khi có thông tin phim." />}
    </section>
    <div className="community-band"><div className="shell"><PositiveFilms /></div></div>
    <section className="shell page-section home-programme">
      <div className="section-heading"><div><p className="eyebrow">Sắp ra mắt</p><h2>Phim sắp chiếu</h2></div><Button to="/movie?status=upcoming" variant="ghost">Xem tất cả <ArrowUpRight size={18} /></Button></div>
      {upcoming.length ? <div className="movie-grid">{upcoming.slice(0, 4).map(f => <MovieCard movie={f} key={f.id} />)}</div> : <PageState title="Chưa có phim sắp chiếu" />}
    </section>
    <EditorialMoment />
  </>;
}
