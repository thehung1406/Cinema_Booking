import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Clock, Play, Ticket, X } from "lucide-react";
import useFilms from "../hooks/useFilms";
import { formatDate } from "../utils/formatters";
import { Button, PageState, Poster } from "./ui/Primitives";
import FilmReviews from "./FilmReviews";

export default function MovieDetail() {
  const { id } = useParams();
  const { data: movie, loading, error, retry } = useFilms(id);
  const [trailerOpen, setTrailerOpen] = useState(false);
  const dialog = useRef(null);
  useEffect(() => {
    if (trailerOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [trailerOpen]);
  useEffect(() => {
    setTrailerOpen(false);
  }, [id]);
  if (loading) return <PageState loading title="Đang tải thông tin phim…" />;
  if (error)
    return (
      <PageState
        title="Chưa tải được thông tin phim"
        message={error}
        onRetry={retry}
      />
    );
  if (!movie)
    return (
      <PageState title="Không tìm thấy phim">
        <Button to="/movie">Khám phá phim khác</Button>
      </PageState>
    );
  const details = [
    ["Thể loại", movie.genre],
    ["Thời lượng", movie.duration],
    ["Khởi chiếu", formatDate(movie.release_date)],
    ["Ngôn ngữ", movie.language],
    ["Phụ đề", movie.subtitle],
    ["Định dạng", movie.formats?.join(", ")],
  ];
  return (
    <>
      <section className="detail-hero">
        <div className="shell grid gap-7 md:grid-cols-[240px_1fr] items-center">
          <Poster
            src={movie.image}
            title={movie.title}
            className="rounded-xl max-w-[200px] md:max-w-none mx-auto"
          />
          <div>
            <p className="text-red-300 text-xs font-bold uppercase tracking-widest">
              Thông tin phim
            </p>
            <h1 className="page-title">{movie.title}</h1>
            <div className="flex flex-wrap gap-3 text-sm text-gray-300 mb-6">
              {movie.rating && (
                <span className="bg-red-700 text-white px-2 py-1 rounded">
                  {movie.rating}
                </span>
              )}
              {movie.duration && (
                <span className="flex gap-2 items-center">
                  <Clock size={16} />
                  {movie.duration}
                </span>
              )}
              {movie.genre && <span>{movie.genre}</span>}
            </div>
            <p className="text-gray-300 mb-6">
              Chọn rạp và suất chiếu để đặt ghế yêu thích của bạn.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button to={`/TicketBooking?filmId=${movie.id}`}>
                <Ticket size={18} />
                Đặt vé ngay
              </Button>
              {movie.trailer && (
                <button
                  className="btn border border-gray-600 text-white"
                  onClick={() => setTrailerOpen(true)}
                >
                  <Play size={16} />
                  Xem trailer
                </button>
              )}
            </div>
          </div>
        </div>
      </section>
      <div className="shell page-section">
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section className="surface">
            <h2 className="text-xl font-bold mb-4">Nội dung phim</h2>
            <p className="text-gray-600 leading-8 whitespace-pre-line">
              {movie.description || "Nội dung phim đang được cập nhật."}
            </p>
          </section>
          <section className="surface">
            <h2 className="text-xl font-bold mb-4">Chi tiết phim</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-5">
              {details.map(([label, value]) => (
                <div key={label}>
                  <dt className="text-gray-500 text-sm mb-1">{label}</dt>
                  <dd className="font-semibold text-sm">
                    {value || "Chưa cập nhật"}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
        <FilmReviews key={movie.id} filmId={movie.id} />
      </div>
      <dialog
        ref={dialog}
        aria-label={`Trailer phim ${movie.title}`}
        onClose={() => setTrailerOpen(false)}
      >
        <div className="bg-white p-3 flex justify-between items-center">
          <h2 className="font-semibold">Trailer phim</h2>
          <button
            className="btn"
            aria-label="Đóng trailer"
            onClick={() => setTrailerOpen(false)}
          >
            <X />
          </button>
        </div>
        {trailerOpen && (
          <iframe
            className="w-full aspect-video"
            src={movie.trailer}
            title={`Trailer ${movie.title}`}
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
          />
        )}
      </dialog>
    </>
  );
}
