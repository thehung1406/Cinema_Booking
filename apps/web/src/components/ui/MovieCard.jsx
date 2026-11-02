import { Clock, Ticket } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, Poster } from "./Primitives";
import { isNowShowing } from "../../utils/filmUtils";
import { formatDate } from "../../utils/formatters";

export default function MovieCard({ movie }) {
  return (
    <article className="movie-card">
      <Link
        to={`/MovieDetail/${movie.id}`}
        className="movie-poster-link"
        aria-label={`Xem chi tiết ${movie.title}`}
      >
        <Poster src={movie.image} title={movie.title} loading="lazy" />
        {movie.rating && <span className="movie-rating">{movie.rating}</span>}
      </Link>
      <div className="movie-card-body">
        <h3>
          <Link to={`/MovieDetail/${movie.id}`} title={movie.title}>
            {movie.title}
          </Link>
        </h3>
        <p className="line-clamp-1">
          {movie.genre || "Chưa cập nhật thể loại"}
        </p>
        <p className="movie-meta">
          <Clock size={14} aria-hidden="true" />
          {movie.duration || "Chưa cập nhật thời lượng"}
        </p>
        {movie.release_date && (
          <p className="text-xs">
            Khởi chiếu: {formatDate(movie.release_date)}
          </p>
        )}
        <Button
          to={`/TicketBooking?filmId=${movie.id}`}
          className="w-full mt-auto"
        >
          <Ticket size={17} aria-hidden="true" />
          {isNowShowing(movie) ? "Đặt vé" : "Xem lịch chiếu"}
        </Button>
      </div>
    </article>
  );
}
