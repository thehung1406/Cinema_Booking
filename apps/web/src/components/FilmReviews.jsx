import { useCallback, useEffect, useState } from "react";
import api from "../config/api";
import { getAccessToken } from "../services/authStorage";
import { Button, PageState } from "./ui/Primitives";
import { formatDate } from "../utils/formatters";
import { Pencil, Trash2, BadgeCheck, MessageSquare } from "lucide-react";
import "./FilmReviews.css";

const labels = {
  positive: "Tích cực",
  neutral: "Trung lập",
  negative: "Tiêu cực",
};
const statuses = {
  pending: "Chờ phân tích",
  failed: "Chưa phân tích được",
  needs_review: "Chờ phân tích lại",
  succeeded: "Đã phân tích",
};
const moderation = {
  pending: "Chưa công khai",
  approved: "Đã công khai",
  rejected: "Không công khai",
};

function ReviewAvatar({ name, avatar }) {
  const [failed, setFailed] = useState(null);
  const parts = (name?.trim() || "Khán giả").split(/\s+/);
  const initials = [parts[0], ...(parts.length > 1 ? [parts.at(-1)] : [])].map(part => Array.from(part)[0]).join("").toLocaleUpperCase("vi");
  const valid = /^(https?:\/\/|\/(?!\/))/.test(avatar || "");
  return <span className="review-avatar" aria-hidden="true"><span>{initials}</span>
    {valid && failed !== avatar && <img src={avatar} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(avatar)} />}
  </span>;
}

function ReviewEntry({ review, own = false, busy, onEdit, onRemove }) {
  return <article className={`review-entry${own ? " review-entry-own" : ""}`}>
    <ReviewAvatar name={review.author} avatar={review.author_avatar} />
    <div className="review-body">
      <div className="review-byline"><strong>{review.author || "Khán giả"}</strong>{own && <span className="review-you">Bạn</span>}
        <time dateTime={review.updated_at}>{formatDate(review.updated_at)}</time></div>
      <div className="review-meta">{review.verified_purchase && <span className="review-purchased"><BadgeCheck size={14} aria-hidden="true" />Đã mua vé</span>}
        <span className={`review-sentiment review-sentiment-${review.sentiment || "pending"}`}>{labels[review.sentiment] || statuses[review.analysis_status]}</span>
        {own && review.moderation_status !== "approved" && <span>{moderation[review.moderation_status]}</span>}</div>
      <p className="review-text">{review.content}</p>
      {own && <div className="review-actions"><button type="button" disabled={busy} onClick={onEdit}><Pencil size={15} aria-hidden="true" />Chỉnh sửa</button>
        <button type="button" className="review-delete" disabled={busy} onClick={onRemove}><Trash2 size={15} aria-hidden="true" />Xóa đánh giá</button></div>}
    </div>
  </article>;
}

export default function FilmReviews({ filmId }) {
  const [summary, setSummary] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [mine, setMine] = useState(null);
  const [content, setContent] = useState("");
  const [editVersion, setEditVersion] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const loggedIn = Boolean(getAccessToken());
  const load = useCallback(
    async (signal) => {
      const [stats, list, own] = await Promise.all([
        api.get(`/films/${filmId}/sentiment-summary`, { signal }),
        api.get(`/films/${filmId}/reviews`, {
          signal,
          params: { skip: page * 20, limit: 20 },
        }),
        loggedIn
          ? api.get(`/films/${filmId}/reviews/mine`, { signal })
          : Promise.resolve({ data: null }),
      ]);
      setSummary(stats.data);
      setReviews(list.data);
      setMine(own.data);
      setLoadError("");
    },
    [filmId, loggedIn, page],
  );
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () =>
      load(controller.signal)
        .catch((e) => {
          if (e.code !== "ERR_CANCELED")
            setLoadError("Chưa tải được đánh giá. Bạn vẫn có thể đặt vé.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [load, attempt]);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = mine
        ? await api.patch(`/reviews/${mine.id}`, {
            content,
            content_version: editVersion ?? mine.content_version,
          })
        : await api.post(`/films/${filmId}/reviews`, { content });
      setContent("");
      setEditVersion(null);
      setNotice(
        data.moderation_status === "approved"
          ? "Đánh giá đã được đăng."
          : "Đã lưu đánh giá. Nội dung chưa công khai.",
      );
      await load();
    } catch (e) {
      setError(
        typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Không lưu được đánh giá.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api.delete(`/reviews/${mine.id}`);
      setContent("");
      setEditVersion(null);
      await load();
    } catch {
      setError("Không xóa được đánh giá. Vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  }
  const publicReviews = reviews.filter(review => review.id !== mine?.id);
  return <section className="surface film-reviews" aria-labelledby="review-title">
    <header className="reviews-heading"><div><p className="reviews-eyebrow">Góc khán giả</p><h2 id="review-title">Cảm nhận về bộ phim</h2></div><MessageSquare size={24} aria-hidden="true" /></header>
    {loading && <PageState loading title="Đang tải đánh giá…" />}
    {loadError && <PageState title="Chưa tải được đánh giá" message={loadError} onRetry={() => setAttempt(v => v + 1)} />}
    {summary && <div className="reviews-overview" aria-label="Tổng hợp cảm xúc">
      <span>{summary.total} nhận xét đã phân tích</span>
      {Object.entries(labels).map(([key, label]) => <span key={key} className={`review-sentiment review-sentiment-${key}`}>{label} <strong>{summary[key]}</strong></span>)}
      {(summary.pending + (summary.needs_review || 0)) > 0 && <span>{summary.pending + (summary.needs_review || 0)} đang phân tích</span>}
    </div>}
    {error && <p role="alert" className="reviews-error">{error}</p>}
    {notice && <p role="status" className="reviews-notice">{notice}</p>}
    {mine && <ReviewEntry review={mine} own busy={busy} onEdit={() => { setContent(mine.content); setEditVersion(mine.content_version); setNotice(""); }} onRemove={remove} />}
    {loggedIn ? (!mine || editVersion !== null) && <form onSubmit={save} className="review-composer">
      <label htmlFor="review-content">{mine ? "Cập nhật cảm nhận" : "Viết cảm nhận về phim"}</label>
      <textarea id="review-content" value={content} onChange={e => setContent(e.target.value)} minLength={5} maxLength={3000}
        required rows={4} autoFocus={Boolean(mine)} placeholder="Chia sẻ điều bạn thích hoặc chưa thích về bộ phim…" />
      <div className="review-composer-footer"><small>Mỗi tài khoản có một nhận xét cho mỗi phim.</small><div>
        {mine && <Button variant="secondary" onClick={() => { setEditVersion(null); setContent(""); }}>Hủy chỉnh sửa</Button>}
        <Button type="submit" busy={busy} disabled={busy || content.trim().length < 5}>{mine ? "Lưu chỉnh sửa" : "Gửi đánh giá"}</Button>
      </div></div>
    </form> : <div className="reviews-login"><Button to="/login" variant="secondary">Đăng nhập để nhận xét</Button></div>}
    <div className="review-list">{publicReviews.map(review => <ReviewEntry key={review.id} review={review} />)}</div>
    {!loading && !loadError && !mine && !reviews.length && <p className="reviews-empty">Chưa có nhận xét. Hãy chia sẻ cảm nhận đầu tiên về bộ phim.</p>}
    {(page > 0 || reviews.length >= 20) && <nav className="reviews-pagination" aria-label="Phân trang nhận xét">
      <Button variant="secondary" disabled={!page} onClick={() => setPage(v => v - 1)}>Trang trước</Button><span>Trang {page + 1}</span>
      <Button variant="secondary" disabled={reviews.length < 20} onClick={() => setPage(v => v + 1)}>Trang sau</Button>
    </nav>}
  </section>;
}
