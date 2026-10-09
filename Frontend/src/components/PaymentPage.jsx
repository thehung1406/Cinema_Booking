import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { CreditCard, ExternalLink, RefreshCw } from "lucide-react";
import api from "../config/api";
import { clearSession, getAccessToken } from "../services/authStorage";
import { formatCurrency, paymentState } from "../utils/formatters";
import { BookingSteps, Button, PageState } from "./ui/Primitives";
import BookingSummary from "./ui/BookingSummary";

export default function PaymentPage() {
  const { bookingId } = useParams();
  const cleanId = bookingId?.split(":")[0];
  const navigate = useNavigate();
  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [paymentError, setPaymentError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    if (!cleanId || !/^\d+$/.test(cleanId)) {
      setError("Mã đơn đặt vé không hợp lệ.");
      setLoading(false);
      return;
    }
    if (!getAccessToken()) {
      navigate("/loginpage");
      return;
    }
    api
      .get(`/bookings/${cleanId}`, { signal: controller.signal })
      .then((r) => {
        setBooking(r.data);
        if (r.data.paymentStatus === "PAID")
          navigate(
            `/payment-result?bookingId=${r.data.id || r.data.bookingId}`,
            { replace: true },
          );
      })
      .catch((e) => {
        if (e.code === "ERR_CANCELED") return;
        if (e.response?.status === 401) {
          clearSession();
          navigate("/loginpage");
        } else
          setError(
            e.response?.status === 404
              ? "Không tìm thấy đơn đặt vé."
              : "Không thể tải đơn đặt vé. Vui lòng thử lại.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [cleanId, navigate, attempt]);
  async function pay() {
    if (!booking || busy || paymentState(booking) !== "pending") return;
    setBusy(true);
    setPaymentError("");
    try {
      const r = await api.post("/payment/vnpay-url", {
        bookingId: booking.id || booking.bookingId,
      });
      if (!r.data.paymentUrl) throw new Error("Missing payment URL");
      window.location.href = r.data.paymentUrl;
    } catch (e) {
      setPaymentError(
        typeof e.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Chưa kết nối được VNPay. Bạn có thể thử lại.",
      );
      setBusy(false);
    }
  }
  if (loading)
    return <PageState loading title="Đang tải thông tin thanh toán…" />;
  if (error)
    return (
      <PageState
        title="Chưa tải được đơn vé"
        message={error}
        onRetry={() => setAttempt((v) => v + 1)}
      >
        <Button to="/user-info" variant="ghost">
          Xem đơn vé trong tài khoản
        </Button>
      </PageState>
    );
  if (!booking) return <PageState title="Chưa có thông tin đơn vé" />;
  const state = paymentState(booking);
  return (
    <div className="shell page-section">
      <BookingSteps current={2} />
      <div className="text-center mb-8">
        <p className="eyebrow">Kiểm tra trước khi thanh toán</p>
        <h1 className="page-title">Hoàn tất đơn vé</h1>
        <p className="text-gray-500">
          Kiểm tra phim, suất chiếu và ghế đã chọn.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_380px] items-start">
        <BookingSummary booking={booking} />
        <section className="surface booking-summary">
          <h2 className="text-xl font-bold flex gap-2 items-center mb-5">
            <CreditCard size={22} className="text-red-700" />
            Thanh toán qua VNPay
          </h2>
          <p className="text-sm text-gray-600 leading-6 mb-5">
            Bạn sẽ được chuyển đến VNPay để chọn phương thức và xác nhận giao
            dịch.
          </p>
          <p
            className={`rounded-lg p-3 text-sm mb-5 ${state === "failed" ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-800"}`}
            role="status"
          >
            {state === "failed"
              ? "Đơn vé đã bị hủy hoặc thanh toán thất bại theo phản hồi từ hệ thống."
              : "Đơn vé đang chờ thanh toán. Trạng thái sẽ được hệ thống xác nhận sau giao dịch."}
          </p>
          {paymentError && (
            <p
              role="alert"
              className="text-sm text-red-700 bg-red-50 p-3 rounded-lg mb-4"
            >
              {paymentError}
            </p>
          )}
          {state === "pending" ? (
            <Button className="w-full" busy={busy} onClick={pay}>
              {busy
                ? "Đang kết nối VNPay…"
                : `Thanh toán ${formatCurrency(booking.totalAmount)}`}
              <ExternalLink size={16} />
            </Button>
          ) : (
            <Button to="/TicketBooking" className="w-full">
              Chọn lịch chiếu khác
            </Button>
          )}
          <Button
            variant="ghost"
            className="w-full mt-2"
            disabled={busy}
            onClick={() => setAttempt((v) => v + 1)}
          >
            <RefreshCw size={16} />
            Kiểm tra trạng thái đơn
          </Button>
          <Button to="/user-info" variant="ghost" className="w-full">
            Xem đơn vé trong tài khoản
          </Button>
        </section>
      </div>
    </div>
  );
}
