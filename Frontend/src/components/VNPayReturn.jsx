import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import QRCode from "react-qr-code";
import { CheckCircle2, CircleHelp, Clock, XCircle } from "lucide-react";
import api from "../config/api";
import { getAccessToken } from "../services/authStorage";
import { paymentStage } from "../services/paymentStage";
import { BookingSteps, Button, PageState } from "./ui/Primitives";
import BookingSummary from "./ui/BookingSummary";

const copies = {
  ISSUED: ["Thanh toán thành công", "Đơn đã được xác nhận và cấp vé. Xem mã vé trong tài khoản của bạn.", CheckCircle2, "text-green-700 bg-green-50"],
  PROCESSING: ["Đã thu tiền — đang xác nhận vé", "Hệ thống đã ghi nhận tiền. Vui lòng chờ xác nhận vé và không thanh toán lại.", Clock, "text-amber-700 bg-amber-50"],
  REQUIRES_REVIEW: ["Giao dịch cần hỗ trợ / đối soát", "Đã ghi nhận tiền nhưng chưa cấp được vé. Liên hệ rạp với mã đơn; không thanh toán lại.", CircleHelp, "text-amber-700 bg-amber-50"],
  FAILED: ["Thanh toán không thành công", "Provider thông báo giao dịch thất bại. Kiểm tra đơn trước khi thử thanh toán lại.", XCircle, "text-red-700 bg-red-50"],
  AWAITING_PAYMENT: ["Đang chờ xác nhận", "Chưa nhận được kết quả thu tiền. Hãy kiểm tra lại trước khi thực hiện giao dịch khác.", Clock, "text-amber-700 bg-amber-50"],
  UNKNOWN: ["Chưa xác minh được giao dịch", "Chưa thể xác định kết quả. Hãy kiểm tra lại hoặc xem đơn trong tài khoản.", CircleHelp, "text-amber-700 bg-amber-50"],
};

export default function VNPayReturn() {
  const location = useLocation();
  const [booking, setBooking] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [stage, setStage] = useState("loading");
  const [message, setMessage] = useState("");
  const [review, setReview] = useState(false);
  const [bookingId, setBookingId] = useState(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true, timer;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    setStage("loading"); setMessage(""); setBooking(null); setTickets([]); setReview(false);
    async function verify() {
      try {
        const response = params.vnp_SecureHash
          ? await api.post("/payment/vnpay-return", params)
          : params.bookingId ? await api.get(`/payment/status/${params.bookingId}`) : null;
        if (!active) return;
        if (!response) throw new Error("Missing transaction");
        const data = response.data, next = paymentStage(data), bid = data.booking_id;
        setStage(next); setMessage(data.message || ""); setReview(Boolean(data.requires_review)); setBookingId(bid);
        if (next === "ISSUED" && bid && getAccessToken()) {
          try {
            const [order, issued] = await Promise.all([api.get(`/bookings/${bid}`), api.get(`/tickets/booking/${bid}`)]);
            if (!active) return;
            if (order.data.bookingStatus !== "CONFIRMED" || order.data.paymentStatus !== "PAID") throw new Error("Booking not confirmed");
            setBooking(order.data);
            setTickets(issued.data.filter(t => ["ISSUED", "USED"].includes(t.status) && t.ticket_code));
          } catch {
            if (active) setMessage("Đã xác nhận vé. Chưa tải được mã vé; kiểm tra lại hoặc xem trong tài khoản.");
          }
        }
        if (["PROCESSING", "AWAITING_PAYMENT"].includes(next)) timer = setTimeout(verify, 3000);
      } catch (e) {
        if (active) {
          setStage("UNKNOWN");
          setMessage(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Chưa thể xác minh kết quả giao dịch. Vui lòng kiểm tra lại.");
        }
      }
    }
    verify();
    return () => { active = false; clearTimeout(timer); };
  }, [location.search, attempt]);
  if (stage === "loading") return <PageState loading title="Đang xác minh kết quả thanh toán…" />;
  const copy = copies[stage], Icon = copy[2];
  return <div className="shell page-section max-w-3xl">
    <BookingSteps current={stage === "ISSUED" ? 4 : 3} />
    <div className="text-center mb-8" role="status">
      <div className={`inline-flex p-4 rounded-full mb-4 ${copy[3]}`}><Icon size={36} aria-hidden="true" /></div>
      <h1 className="page-title">{copy[0]}</h1><p className="text-gray-600 leading-7">{message || copy[1]}</p>
      {bookingId && <p className="mt-2">Mã đơn: {bookingId}</p>}
      {review && stage === "ISSUED" && <p className="text-amber-800 mt-2">Vé đã cấp; có khoản thu cần đối soát. Liên hệ rạp và không thanh toán lại.</p>}
    </div>
    {booking && <BookingSummary booking={booking} />}
    {stage === "ISSUED" && tickets.length > 0 && <section className="surface mt-5">
      <h2 className="font-bold text-lg mb-4">Vé điện tử của bạn</h2>
      <div className="flex flex-wrap gap-6">{tickets.map(ticket => <div key={ticket.ticket_code} className="bg-white p-3 max-w-full">
        <QRCode value={ticket.ticket_code} size={130} level="H" role="img" aria-label={`Mã QR vé ${ticket.ticket_code}`} />
        <p className="text-xs mt-3 break-all max-w-48">{ticket.ticket_code}</p><p>{ticket.status === "USED" ? "Đã sử dụng" : "Đã cấp vé"}</p>
      </div>)}</div>
    </section>}
    <div className="flex flex-wrap gap-3 justify-center mt-6">
      <Button onClick={() => setAttempt(v => v + 1)}>Kiểm tra lại trạng thái</Button>
      <Button to="/user-info" variant="secondary">Xem đơn vé trong tài khoản</Button>
      <Button to="/" variant="ghost">Về trang chủ</Button>
    </div>
  </div>;
}
