import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { QRCode } from "react-qr-code";
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Film, 
  MapPin, 
  Calendar, 
  Ticket, 
  Home, 
  User, 
  RefreshCw, 
  ShieldCheck, 
  CreditCard, 
  Clock,
  Loader2 
} from "lucide-react";
import api from "../config/api";
import logger from '../utils/logger';

const VNPAY_RESPONSE_MESSAGES = {
  "00": "Giao dịch thành công",
  "07": "Trừ tiền thành công. Giao dịch bị nghi ngờ (liên quan tới lừa đảo, bất thường).",
  "09": "Thẻ/Tài khoản của bạn chưa đăng ký dịch vụ Internet Banking.",
  "10": "Xác thực thông tin thẻ/tài khoản không đúng quá 3 lần.",
  "11": "Đã hết hạn chờ thanh toán. Giao dịch đã bị hủy.",
  "12": "Thẻ/Tài khoản của bạn đang bị khóa.",
  "13": "Bạn đã nhập sai mật khẩu xác thực OTP.",
  "24": "Bạn đã hủy giao dịch thanh toán.",
  "51": "Tài khoản của bạn không đủ số dư để thực hiện giao dịch.",
  "65": "Tài khoản của bạn đã vượt quá hạn mức giao dịch trong ngày.",
  "75": "Ngân hàng thanh toán đang bảo trì.",
  "79": "Nhập sai mật khẩu thanh toán quá số lần quy định.",
  "99": "Giao dịch không thành công do lỗi hệ thống VNPay."
};

const VNPayReturn = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [booking, setBooking] = useState(null);
  const [status, setStatus] = useState("loading"); // "loading" | "success" | "failed" | "error"
  const [errorMessage, setErrorMessage] = useState("");
  const [vnpayInfo, setVnpayInfo] = useState({});

  useEffect(() => {
    const processReturn = async () => {
      const searchParams = new URLSearchParams(location.search);
      const params = Object.fromEntries(searchParams.entries());

      const vnp_ResponseCode = params.vnp_ResponseCode;
      const vnp_TxnRef = params.vnp_TxnRef || params.bookingId;

      setVnpayInfo(params);

      // Internal redirect for already-paid bookings: verify from backend first.
      if (!params.vnp_SecureHash) {
        if (params.bookingId) {
          try {
            const bookingRes = await api.get(`/bookings/${params.bookingId}`);
            if (bookingRes.data?.paymentStatus === "PAID") {
              setBooking(bookingRes.data);
              setStatus("success");
            } else {
              setBooking(bookingRes.data);
              setErrorMessage("Đơn hàng chưa được xác nhận thanh toán.");
              setStatus("failed");
            }
          } catch (err) {
            logger.error("Lỗi khi kiểm tra trạng thái booking:", err);
            setErrorMessage(err.response?.data?.detail || "Không thể xác thực trạng thái thanh toán.");
            setStatus("error");
          }
          return;
        }

        setErrorMessage("Không tìm thấy thông tin phản hồi từ cổng thanh toán.");
        setStatus("error");
        return;
      }

      try {
        // Gọi backend để xác thực chữ ký và cập nhật DB
        const res = await api.post("/payment/vnpay-return", {
          ...params,
          bookingId: vnp_TxnRef
        });

        if (res.data.status === "success" && vnp_ResponseCode === "00") {
          setBooking(res.data.booking);
          setStatus("success");
        } else {
          setBooking(res.data.booking);
          setStatus("failed");
          const msg = VNPAY_RESPONSE_MESSAGES[vnp_ResponseCode] || res.data.message || "Giao dịch thất bại.";
          setErrorMessage(msg);
        }
      } catch (err) {
        logger.error("Lỗi khi xác nhận giao dịch VNPay:", err);
        setStatus("error");
        setErrorMessage(
          err.response?.data?.detail || "Không thể xác thực chữ ký giao dịch từ VNPay. Vui lòng liên hệ bộ phận hỗ trợ."
        );
      }
    };

    processReturn();
  }, [location.search]);

  const formatCurrency = (val) => {
    if (!val) return "0";
    return Number(val).toLocaleString("vi-VN");
  };

  const formatVnpDate = (dateStr) => {
    if (!dateStr || dateStr.length !== 14) return dateStr || "N/A";
    const year = dateStr.substring(0, 4);
    const month = dateStr.substring(4, 6);
    const day = dateStr.substring(6, 8);
    const hour = dateStr.substring(8, 10);
    const minute = dateStr.substring(10, 12);
    const second = dateStr.substring(12, 14);
    return `${hour}:${minute}:${second} - ${day}/${month}/${year}`;
  };

  if (status === "loading") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-950 text-white px-4">
        <Loader2 className="w-14 h-14 text-red-600 animate-spin mb-4" />
        <h2 className="text-xl font-bold mb-2">Đang xác thực kết quả giao dịch...</h2>
        <p className="text-gray-400 text-sm">Vui lòng không tắt hoặc tải lại trang</p>
      </div>
    );
  }

  const isSuccess = status === "success";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        {/* Status Header */}
        <div className="text-center mb-8">
          {isSuccess ? (
            <div className="inline-flex items-center justify-center w-20 h-20 bg-green-500/20 text-green-500 rounded-full mb-4 ring-8 ring-green-500/10 animate-pulse">
              <CheckCircle2 className="w-12 h-12" />
            </div>
          ) : (
            <div className="inline-flex items-center justify-center w-20 h-20 bg-red-500/20 text-red-500 rounded-full mb-4 ring-8 ring-red-500/10">
              <XCircle className="w-12 h-12" />
            </div>
          )}

          <h1 className="text-3xl font-extrabold text-white mb-2">
            {isSuccess ? "Thanh toán thành công!" : "Thanh toán không thành công"}
          </h1>
          <p className="text-gray-400 text-sm max-w-md mx-auto">
            {isSuccess 
              ? "Cảm ơn bạn đã đặt vé. Thông tin vé điện tử của bạn đã được ghi nhận và gửi qua email."
              : errorMessage || "Giao dịch qua cổng VNPay không thành công hoặc đã bị hủy."}
          </p>
        </div>

        {/* Success Card: Cinema E-Ticket */}
        {isSuccess && booking ? (
          <div className="space-y-6">
            {/* E-Ticket Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-3xl overflow-hidden shadow-2xl relative">
              {/* Top Banner */}
              <div className="bg-gradient-to-r from-red-700 via-red-600 to-red-800 p-4 text-white flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <Film className="w-5 h-5" />
                  <span className="font-bold tracking-wider text-sm uppercase">Vé xem phim điện tử</span>
                </div>
                <span className="text-xs font-mono bg-black/30 px-3 py-1 rounded-full border border-white/20">
                  Mã đơn: #{booking.id || vnpayInfo.vnp_TxnRef}
                </span>
              </div>

              {/* Ticket Body */}
              <div className="p-6 space-y-6">
                <div className="flex gap-4 items-start">
                  {booking.filmImage && (
                    <img 
                      src={booking.filmImage} 
                      alt={booking.filmTitle || "Phim"} 
                      className="w-24 h-36 object-cover rounded-xl shadow-md flex-shrink-0"
                      onError={(e) => { e.target.style.display = "none"; }}
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-2xl font-black text-white truncate mb-2">
                      {booking.filmTitle || "Vé Xem Phim"}
                    </h3>
                    <div className="space-y-1 text-sm text-gray-300">
                      <div className="flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-red-500 flex-shrink-0" />
                        <span>{booking.theaterName} • {booking.roomName}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-red-500 flex-shrink-0" />
                        <span>
                          {booking.showDate ? new Date(booking.showDate).toLocaleDateString('vi-VN') : "N/A"} 
                          {booking.startTime ? ` • ${booking.startTime.substring(0, 5)}` : ""}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-red-500 flex-shrink-0" />
                        <span>Khách hàng: {booking.fullName || "Khách hàng"}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Seats List */}
                <div className="bg-gray-950 p-4 rounded-2xl border border-gray-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Danh sách ghế:</span>
                    <span className="text-xs font-bold text-red-400">
                      {booking.seats?.length || 1} ghế
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {booking.seats && booking.seats.map((seat, idx) => (
                      <span 
                        key={idx}
                        className="px-3 py-1 bg-red-600/20 border border-red-600/40 text-red-300 font-bold rounded-lg text-sm"
                      >
                        {seat.seat_name || seat.seatName} ({seat.seat_type || "Thường"})
                      </span>
                    ))}
                  </div>
                </div>

                {/* Perforated Divider */}
                <div className="relative flex items-center justify-center my-4">
                  <div className="absolute -left-10 w-6 h-6 bg-gray-950 rounded-full"></div>
                  <div className="w-full border-b-2 border-dashed border-gray-800"></div>
                  <div className="absolute -right-10 w-6 h-6 bg-gray-950 rounded-full"></div>
                </div>

                {/* QR Code & Check-in info */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-6 pt-2">
                  <div className="space-y-2 text-center sm:text-left flex-1">
                    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Tổng tiền thanh toán</div>
                    <div className="text-3xl font-extrabold text-red-500">
                      {formatCurrency(booking.totalAmount || (vnpayInfo.vnp_Amount ? Number(vnpayInfo.vnp_Amount) / 100 : 0))} VNĐ
                    </div>
                    <div className="text-xs text-gray-400">
                      Cổng thanh toán: <span className="font-semibold text-white">VNPay Sandbox</span>
                    </div>
                    {vnpayInfo.vnp_TransactionNo && (
                      <div className="text-xs text-gray-400">
                        Mã GD VNPay: <span className="font-mono text-gray-300">{vnpayInfo.vnp_TransactionNo}</span>
                      </div>
                    )}
                    {vnpayInfo.vnp_PayDate && (
                      <div className="text-xs text-gray-400">
                        Thời gian: <span className="text-gray-300">{formatVnpDate(vnpayInfo.vnp_PayDate)}</span>
                      </div>
                    )}
                  </div>

                  <div className="bg-white p-3 rounded-2xl shadow-lg text-center flex flex-col items-center">
                    <QRCode
                      value={JSON.stringify({
                        bookingId: booking.id,
                        film: booking.filmTitle,
                        seats: booking.seats?.map(s => s.seat_name || s.seatName).join(", "),
                        showtime: `${booking.showDate} ${booking.startTime}`,
                        vnpTxn: vnpayInfo.vnp_TransactionNo || ""
                      })}
                      size={130}
                      level="H"
                    />
                    <span className="text-[10px] text-gray-600 font-bold mt-1.5 uppercase">Quét tại quầy vé</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 pt-2">
              <button
                onClick={() => navigate("/user-info")}
                className="flex-1 py-3.5 px-6 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-red-900/30 transition"
              >
                <Ticket className="w-5 h-5" />
                Xem vé trong tài khoản
              </button>
              <button
                onClick={() => navigate("/")}
                className="flex-1 py-3.5 px-6 bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-200 rounded-xl font-bold flex items-center justify-center gap-2 transition"
              >
                <Home className="w-5 h-5" />
                Về trang chủ
              </button>
            </div>
          </div>
        ) : (
          /* Failure Card */
          <div className="space-y-6">
            <div className="bg-gray-900 border border-red-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
              <div className="flex items-center gap-3 text-red-400 border-b border-gray-800 pb-4">
                <AlertTriangle className="w-6 h-6 flex-shrink-0" />
                <span className="font-bold text-lg">Chi tiết lỗi giao dịch</span>
              </div>

              <div className="space-y-3 text-sm text-gray-300">
                <div className="flex justify-between py-2 border-b border-gray-800/60">
                  <span className="text-gray-500">Mã đơn đặt vé:</span>
                  <span className="font-bold text-white">#{vnpayInfo.vnp_TxnRef || "N/A"}</span>
                </div>
                {vnpayInfo.vnp_ResponseCode && (
                  <div className="flex justify-between py-2 border-b border-gray-800/60">
                    <span className="text-gray-500">Mã phản hồi VNPay:</span>
                    <span className="font-mono font-semibold text-red-400">{vnpayInfo.vnp_ResponseCode}</span>
                  </div>
                )}
                {vnpayInfo.vnp_BankCode && (
                  <div className="flex justify-between py-2 border-b border-gray-800/60">
                    <span className="text-gray-500">Ngân hàng:</span>
                    <span className="font-semibold text-white">{vnpayInfo.vnp_BankCode}</span>
                  </div>
                )}
                {vnpayInfo.vnp_Amount && (
                  <div className="flex justify-between py-2 border-b border-gray-800/60">
                    <span className="text-gray-500">Số tiền:</span>
                    <span className="font-bold text-white">
                      {formatCurrency(Number(vnpayInfo.vnp_Amount) / 100)} VNĐ
                    </span>
                  </div>
                )}
                <div className="py-2 text-xs text-gray-400 bg-gray-950 p-3 rounded-xl border border-gray-800">
                  Lưu ý: Ghế đã chọn của đơn hàng này đã được tự động giải phóng để khách hàng khác có thể đặt. Quý khách có thể chọn lại suất chiếu và tiến hành đặt vé mới.
                </div>
              </div>
            </div>

            {/* Failure Actions */}
            <div className="flex flex-col sm:flex-row gap-4">
              <button
                onClick={() => navigate("/movie")}
                className="flex-1 py-3.5 px-6 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-red-900/30 transition"
              >
                <RefreshCw className="w-5 h-5" />
                Đặt vé lại
              </button>
              <button
                onClick={() => navigate("/")}
                className="flex-1 py-3.5 px-6 bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-200 rounded-xl font-bold flex items-center justify-center gap-2 transition"
              >
                <Home className="w-5 h-5" />
                Về trang chủ
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VNPayReturn;
