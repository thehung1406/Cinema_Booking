import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import QRCode from "react-qr-code";
import { CheckCircle2, CircleHelp, Clock, XCircle } from "lucide-react";
import api from "../config/api";
import { paymentState } from "../utils/formatters";
import { BookingSteps, Button, PageState } from "./ui/Primitives";
import BookingSummary from "./ui/BookingSummary";

export default function VNPayReturn() {
  const location = useLocation();
  const [booking, setBooking] = useState(null);
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    setStatus("loading");
    setMessage("");
    setBooking(null);
    async function verify() {
      try {
        if (params.vnp_SecureHash) {
          const r = await api.post("/payment/vnpay-return", {
            ...params,
            bookingId: params.vnp_TxnRef || params.bookingId,
          });
          if (!active) return;
          setBooking(r.data.booking);
          setStatus(
            r.data.status === "success"
              ? "success"
              : r.data.status === "failed"
                ? "failed"
                : "pending",
          );
          setMessage(r.data.message || "");
        } else if (params.bookingId) {
          const r = await api.get(`/bookings/${params.bookingId}`);
          if (!active) return;
          setBooking(r.data);
          setStatus(paymentState(r.data));
        } else {
          if (active) {
            setStatus("error");
            setMessage(
              "Thiếu thông tin để kiểm tra kết quả giao dịch. Hãy kiểm tra đơn vé trong tài khoản.",
            );
          }
        }
      } catch (e) {
        if (active) {
          setStatus("error");
          setMessage(
            typeof e.response?.data?.detail === "string"
              ? e.response.data.detail
              : "Chưa thể xác minh kết quả giao dịch. Vui lòng kiểm tra lại.",
          );
        }
      }
    }
    verify();
    return () => {
      active = false;
    };
  }, [location.search, attempt]);
  if (status === "loading")
    return (
      <PageState
        loading
        title="Đang xác minh kết quả thanh toán…"
        message="Đang kiểm tra phản hồi giao dịch với hệ thống."
      />
    );
  const copy = {
    success: [
      "Thanh toán thành công",
      "Đơn vé của bạn đã được hệ thống xác nhận.",
      CheckCircle2,
      "text-green-700 bg-green-50",
    ],
    failed: [
      "Thanh toán không thành công",
      "Hệ thống xác nhận giao dịch thất bại hoặc đơn vé đã bị hủy.",
      XCircle,
      "text-red-700 bg-red-50",
    ],
    pending: [
      "Đang chờ xác nhận",
      "Đơn vé chưa được xác nhận thanh toán. Hãy kiểm tra lại trạng thái trước khi thực hiện giao dịch khác.",
      Clock,
      "text-amber-700 bg-amber-50",
    ],
    error: [
      "Chưa xác minh được giao dịch",
      "Chưa thể xác định thanh toán thành công hay thất bại. Hãy kiểm tra lại hoặc xem đơn vé trong tài khoản.",
      CircleHelp,
      "text-amber-700 bg-amber-50",
    ],
  }[status];
  const Icon = copy[2];
  return (
    <div className="shell page-section max-w-3xl">
      <BookingSteps current={status === "success" ? 3 : 2} />
      <div className="text-center mb-8" role="status">
        <div className={`inline-flex p-4 rounded-full mb-4 ${copy[3]}`}>
          <Icon size={36} aria-hidden="true" />
        </div>
        <h1 className="page-title">{copy[0]}</h1>
        <p className="text-gray-600 leading-7">{message || copy[1]}</p>
      </div>
      {booking && <BookingSummary booking={booking} />}
      {status === "success" && booking && (
        <section className="surface mt-5 flex flex-col sm:flex-row items-center gap-6">
          <div className="bg-white p-3 shrink-0">
            <QRCode
              value={JSON.stringify({
                bookingId: booking.id,
                film: booking.filmTitle,
                seats: booking.seats
                  ?.map((s) => s.seat_name || s.seatName)
                  .join(", "),
                showtime: `${booking.showDate} ${booking.startTime}`,
                vnpTxn:
                  new URLSearchParams(location.search).get(
                    "vnp_TransactionNo",
                  ) || "",
              })}
              size={130}
              level="H"
            />
          </div>
          <div>
            <h2 className="font-bold text-lg mb-2">Vé điện tử của bạn</h2>
            <p className="text-sm text-gray-600 leading-6">
              Lưu thông tin đơn vé và mã QR để xuất trình tại quầy vé.
            </p>
          </div>
        </section>
      )}
      <div className="flex flex-wrap gap-3 justify-center mt-6">
        {["pending", "error"].includes(status) && (
          <Button onClick={() => setAttempt((v) => v + 1)}>
            Kiểm tra lại trạng thái
          </Button>
        )}
        {status === "failed" && (
          <Button to="/TicketBooking">Chọn lịch chiếu khác</Button>
        )}
        <Button
          to="/user-info"
          variant={status === "success" ? "primary" : "secondary"}
        >
          Xem đơn vé trong tài khoản
        </Button>
        <Button to="/" variant="ghost">
          Về trang chủ
        </Button>
      </div>
    </div>
  );
}
