import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Edit3, UserRound } from "lucide-react";
import api from "../config/api";
import {
  clearSession,
  getAccessToken,
  getCurrentUser,
  updateCurrentUser,
} from "../services/authStorage";
import { paymentState } from "../utils/formatters";
import { Button, FormField, PageState } from "./ui/Primitives";
import BookingSummary from "./ui/BookingSummary";

export default function UserInfo() {
  const navigate = useNavigate();
  const [user, setUser] = useState(getCurrentUser);
  const [form, setForm] = useState(() => getCurrentUser() || {});
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [bookings, setBookings] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [sort, setSort] = useState("newest");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!user || !getAccessToken()) {
      navigate("/loginpage");
      return;
    }
    const controller = new AbortController();
    setHistoryLoading(true);
    setHistoryError("");
    api
      .get("/bookings", { signal: controller.signal })
      .then((r) => setBookings(r.data))
      .catch((e) => {
        if (e.code === "ERR_CANCELED") return;
        if (e.response?.status === 401) {
          clearSession();
          navigate("/loginpage");
        } else
          setHistoryError("Không thể tải lịch sử đặt vé. Vui lòng thử lại.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [navigate, user, attempt]);
  async function save(e) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = new FormData();
      Object.keys(form).forEach((key) => {
        if (
          ![
            "avatar",
            "created_at",
            "role",
            "access_token",
            "refresh_token",
            "token_type",
          ].includes(key)
        )
          payload.append(key, form[key] ?? "");
      });
      const r = await api.put("/user/profile", payload);
      if (!r.data.success)
        throw new Error(r.data.message || "Cập nhật thông tin thất bại.");
      const updated = updateCurrentUser(r.data.user);
      setUser(updated);
      setForm(updated);
      setEditing(false);
      setSuccess("Thông tin tài khoản đã được cập nhật.");
    } catch (err) {
      setError(
        typeof err.response?.data?.detail === "string"
          ? err.response.data.detail
          : err.message || "Không thể lưu thông tin. Vui lòng thử lại.",
      );
    } finally {
      setSaving(false);
    }
  }
  if (!user) return <PageState loading title="Đang tải tài khoản…" />;
  const sorted = [...bookings].sort((a, b) =>
    sort === "amount_high"
      ? Number(b.totalAmount) - Number(a.totalAmount)
      : sort === "amount_low"
        ? Number(a.totalAmount) - Number(b.totalAmount)
        : sort === "oldest"
          ? new Date(a.bookingDate) - new Date(b.bookingDate)
          : new Date(b.bookingDate) - new Date(a.bookingDate),
  );
  const statusCopy = {
    success: ["Đã thanh toán", "text-green-800 bg-green-50"],
    pending: ["Chờ thanh toán", "text-amber-800 bg-amber-50"],
    failed: ["Đã hủy / Thanh toán thất bại", "text-red-800 bg-red-50"],
  };
  return (
    <div className="shell page-section">
      <p className="eyebrow">Tài khoản của bạn</p>
      <h1 className="page-title">Thông tin & đơn vé</h1>
      <p className="text-gray-500 mb-8">
        Quản lý thông tin cá nhân và theo dõi các buổi xem phim.
      </p>
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)] items-start">
        <section className="surface">
          <div className="flex gap-3 items-center mb-6">
            <span className="p-3 bg-red-50 rounded-full text-red-700 shrink-0">
              <UserRound />
            </span>
            <div className="min-w-0">
              <h2 className="font-bold text-lg">
                {user.full_name || user.username}
              </h2>
              <p className="text-sm text-gray-500 break-all">
                @{user.username}
              </p>
            </div>
          </div>
          {error && (
            <p
              role="alert"
              className="text-red-800 bg-red-50 p-3 rounded-lg text-sm mb-4"
            >
              {error}
            </p>
          )}
          {success && (
            <p
              role="status"
              className="text-green-800 bg-green-50 p-3 rounded-lg text-sm mb-4"
            >
              {success}
            </p>
          )}
          {editing ? (
            <form onSubmit={save} className="space-y-4" aria-busy={saving}>
              {[
                ["full_name", "Họ và tên", "text", "name"],
                ["email", "Email", "email", "email"],
                ["phone", "Số điện thoại", "tel", "tel"],
              ].map(([name, label, type, autoComplete]) => (
                <FormField
                  key={name}
                  id={name}
                  name={name}
                  label={label}
                  type={type}
                  autoComplete={autoComplete}
                  value={form[name] || ""}
                  onChange={(e) =>
                    setForm((old) => ({ ...old, [name]: e.target.value }))
                  }
                  required={name !== "phone"}
                  disabled={saving}
                />
              ))}
              <div className="flex gap-3">
                <Button type="submit" busy={saving} className="flex-1">
                  {saving ? "Đang lưu…" : "Lưu thông tin"}
                </Button>
                <Button
                  variant="secondary"
                  disabled={saving}
                  onClick={() => {
                    setForm(user);
                    setEditing(false);
                    setError("");
                  }}
                >
                  Hủy
                </Button>
              </div>
            </form>
          ) : (
            <>
              <dl className="space-y-4 mb-6">
                {[
                  ["Họ và tên", user.full_name],
                  ["Email", user.email],
                  ["Số điện thoại", user.phone],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-sm text-gray-500 mb-1">{label}</dt>
                    <dd className="text-sm font-semibold break-all">
                      {value || "Chưa cập nhật"}
                    </dd>
                  </div>
                ))}
              </dl>
              <Button
                variant="secondary"
                className="w-full"
                onClick={() => {
                  setEditing(true);
                  setSuccess("");
                }}
              >
                <Edit3 size={16} />
                Chỉnh sửa thông tin
              </Button>
            </>
          )}
        </section>
        <section className="min-w-0">
          <div className="section-heading">
            <h2>Lịch sử đặt vé</h2>
            <select
              aria-label="Sắp xếp đơn vé"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="border border-gray-300 bg-white rounded-lg px-3 text-sm"
            >
              <option value="newest">Mới nhất</option>
              <option value="oldest">Cũ nhất</option>
              <option value="amount_high">Giá cao nhất</option>
              <option value="amount_low">Giá thấp nhất</option>
            </select>
          </div>
          {historyLoading ? (
            <PageState loading title="Đang tải lịch sử đặt vé…" />
          ) : historyError ? (
            <PageState
              title="Chưa tải được đơn vé"
              message={historyError}
              onRetry={() => setAttempt((v) => v + 1)}
            />
          ) : !sorted.length ? (
            <PageState
              title="Chưa có đơn vé"
              message="Khám phá phim và đặt vé cho buổi xem tiếp theo."
            >
              <Button to="/movie">Khám phá phim</Button>
            </PageState>
          ) : (
            <div className="space-y-5">
              {sorted.map((booking) => {
                const state = paymentState(booking);
                const copy = statusCopy[state];
                return (
                  <article key={booking.id}>
                    <BookingSummary booking={booking} />
                    <div className="flex flex-wrap justify-between items-center gap-3 px-4 py-3">
                      <span
                        className={`rounded-full px-3 py-2 text-xs font-semibold ${copy[1]}`}
                      >
                        {copy[0]}
                      </span>
                      {state === "pending" ? (
                        <Link
                          className="btn btn-primary"
                          to={`/payment/${booking.id}`}
                        >
                          Tiếp tục thanh toán
                        </Link>
                      ) : state === "success" ? (
                        <Link
                          className="btn btn-ghost"
                          to={`/payment-result?bookingId=${booking.id}`}
                        >
                          Xem vé điện tử →
                        </Link>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
