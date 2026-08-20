import React, { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { 
  Clock, 
  Film, 
  MapPin, 
  Calendar, 
  CreditCard, 
  ShieldCheck, 
  AlertCircle, 
  ArrowLeft, 
  Loader2, 
  CheckCircle2, 
  Ticket 
} from "lucide-react";
import api from "../config/api";
import { clearSession, getAccessToken } from "../services/authStorage";
import logger from '../utils/logger';

const PaymentPage = () => {
  const { bookingId } = useParams();
  const navigate = useNavigate();
  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expired, setExpired] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(600);
  const [isRedirecting, setIsRedirecting] = useState(false);

  // Clean bookingId
  const cleanBookingId = useMemo(() => {
    return bookingId ? bookingId.split(':')[0] : null;
  }, [bookingId]);

  // Lấy thông tin booking từ API
  useEffect(() => {
    const fetchData = async () => {
      try {
        if (!cleanBookingId || isNaN(cleanBookingId)) {
          setError("Mã đơn đặt vé không hợp lệ");
          setLoading(false);
          return;
        }

        if (!getAccessToken()) {
          navigate('/loginpage');
          return;
        }

        const response = await api.get(`/bookings/${cleanBookingId}`);
        setBooking(response.data);
        
        // Nếu đơn hàng đã được thanh toán, chuyển hướng đến trang kết quả
        if (response.data.paymentStatus === "PAID") {
          navigate(`/payment-result?bookingId=${response.data.id || response.data.bookingId}`);
        }
        
        setLoading(false);
      } catch (err) {
        logger.error("Lỗi khi lấy thông tin booking:", err);
        if (err.response && err.response.status === 401) {
          clearSession();
          navigate('/loginpage');
        } else if (err.response && err.response.status === 404) {
          setError("Không tìm thấy thông tin đơn đặt vé.");
        } else {
          setError("Không thể tải thông tin đặt vé. Vui lòng thử lại sau.");
        }
        setLoading(false);
      }
    };
    fetchData();
  }, [cleanBookingId, navigate]);

  // Đếm ngược 10 phút kể từ bookingDate
  useEffect(() => {
    if (!booking || !booking.bookingDate) return;
    
    let bookingDateStr = booking.bookingDate;
    if (!bookingDateStr.endsWith('Z') && !bookingDateStr.includes('+')) {
      bookingDateStr = bookingDateStr + 'Z';
    }
    
    const bookingTime = new Date(bookingDateStr).getTime();
    if (isNaN(bookingTime)) {
      logger.error("Invalid booking date:", booking.bookingDate);
      return;
    }
    
    const expireTime = bookingTime + 10 * 60 * 1000;
    
    const updateCountdown = () => {
      const now = Date.now();
      const diff = Math.max(0, Math.floor((expireTime - now) / 1000));
      setSecondsLeft(diff);
      if (diff === 0) setExpired(true);
    };
    
    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
    return () => clearInterval(timer);
  }, [booking]);

  // Khi hết giờ, tự động hủy booking
  useEffect(() => {
    if (expired && booking && cleanBookingId) {
      api.patch(`/bookings/${cleanBookingId}/payment-status?payment_status=FAILED`).catch(err => {
        logger.warn("Lỗi khi cập nhật trạng thái hủy đơn:", err);
      });
    }
  }, [expired, booking, cleanBookingId]);

  const handleVNPay = async () => {
    if (!booking || expired || isRedirecting) return;
    try {
      setIsRedirecting(true);
      const res = await api.post('/payment/vnpay-url', {
        bookingId: booking.id
      });
      if (res.data && res.data.paymentUrl) {
        window.location.href = res.data.paymentUrl;
      } else {
        throw new Error("Không nhận được URL thanh toán từ máy chủ");
      }
    } catch (err) {
      logger.error("Lỗi tạo URL thanh toán:", err);
      setError(err.response?.data?.detail || "Không thể kết nối đến cổng thanh toán VNPay. Vui lòng thử lại.");
      setIsRedirecting(false);
    }
  };

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gray-900 text-white">
        <Loader2 className="w-12 h-12 text-red-600 animate-spin mb-4" />
        <p className="text-gray-300 font-medium">Đang tải thông tin thanh toán...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 px-4">
        <div className="bg-gray-800 border border-gray-700 p-8 rounded-2xl max-w-md w-full text-center text-white shadow-2xl">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Thông báo</h2>
          <p className="text-gray-300 mb-6">{error}</p>
          <button 
            onClick={() => navigate("/")}
            className="w-full py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold transition"
          >
            Quay về trang chủ
          </button>
        </div>
      </div>
    );
  }

  if (!booking) return null;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Step Indicator */}
        <div className="flex items-center justify-center mb-8 gap-4 text-sm font-medium">
          <div className="flex items-center text-gray-500">
            <span className="w-7 h-7 rounded-full bg-gray-800 flex items-center justify-center mr-2 text-xs">1</span>
            Chọn ghế
          </div>
          <div className="w-12 h-[2px] bg-red-600"></div>
          <div className="flex items-center text-red-500 font-bold">
            <span className="w-7 h-7 rounded-full bg-red-600 text-white flex items-center justify-center mr-2 text-xs">2</span>
            Thanh toán
          </div>
          <div className="w-12 h-[2px] bg-gray-800"></div>
          <div className="flex items-center text-gray-500">
            <span className="w-7 h-7 rounded-full bg-gray-800 flex items-center justify-center mr-2 text-xs">3</span>
            Nhận vé
          </div>
        </div>

        {expired ? (
          <div className="bg-gray-900 border border-red-500/50 rounded-2xl p-8 text-center shadow-2xl max-w-lg mx-auto">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4 animate-bounce" />
            <h3 className="text-2xl font-bold text-red-500 mb-2">Đã hết thời gian thanh toán!</h3>
            <p className="text-gray-400 mb-6">
              Đơn đặt vé #{booking.id} đã bị hủy do quá thời hạn giữ ghế (10 phút). Vui lòng đặt vé lại.
            </p>
            <button
              onClick={() => navigate("/movie")}
              className="w-full py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold transition"
            >
              Chọn suất chiếu khác
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Cột trái: Thông tin đơn hàng & Phim */}
            <div className="lg:col-span-7 space-y-6">
              {/* Countdown Timer Card */}
              <div className={`p-5 rounded-2xl border transition-all ${
                secondsLeft < 120 
                  ? "bg-red-950/40 border-red-500/70 animate-pulse" 
                  : "bg-gray-900/90 border-gray-800"
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Clock className={`w-6 h-6 ${secondsLeft < 120 ? "text-red-500" : "text-amber-400"}`} />
                    <div>
                      <h4 className="text-sm font-medium text-gray-300">Thời gian giữ vé còn lại</h4>
                      <p className="text-xs text-gray-500">Vé sẽ tự động giải phóng khi hết giờ</p>
                    </div>
                  </div>
                  <div className="text-3xl font-extrabold font-mono tracking-wider text-red-500">
                    {formatTime(secondsLeft)}
                  </div>
                </div>
              </div>

              {/* Movie & Showtime Details */}
              <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
                <div className="p-6">
                  <div className="flex gap-4">
                    {booking.filmImage && (
                      <img
                        src={booking.filmImage}
                        alt={booking.filmTitle || "Poster"}
                        className="w-28 h-40 object-cover rounded-xl shadow-md flex-shrink-0"
                        onError={(e) => { e.target.style.display = "none"; }}
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-600/20 text-red-400 border border-red-600/30 mb-2">
                        Mã đơn #{booking.id}
                      </span>
                      <h3 className="text-xl font-bold text-white truncate mb-2">
                        {booking.filmTitle || "Phim chiếu rạp"}
                      </h3>
                      
                      <div className="space-y-1.5 text-sm text-gray-400">
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4 text-gray-500 flex-shrink-0" />
                          <span className="truncate">{booking.theaterName} • {booking.roomName}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-gray-500 flex-shrink-0" />
                          <span>
                            {booking.showDate ? new Date(booking.showDate).toLocaleDateString('vi-VN') : ""}
                            {booking.startTime ? ` • ${booking.startTime.substring(0, 5)}` : ""}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Ticket className="w-4 h-4 text-gray-500 flex-shrink-0" />
                          <span>
                            {booking.seats && booking.seats.length > 0 
                              ? `${booking.seats.length} vé` 
                              : "1 vé"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Danh sách ghế đã chọn */}
                  <div className="mt-6 pt-5 border-t border-gray-800">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                      Ghế đã chọn
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {booking.seats && booking.seats.map((seat, index) => (
                        <div 
                          key={index}
                          className="px-3 py-1.5 bg-gray-800/80 border border-gray-700 rounded-lg text-sm flex items-center gap-2"
                        >
                          <span className="font-bold text-red-400">{seat.seat_name || seat.seatName}</span>
                          <span className="text-xs text-gray-400 font-medium">({seat.seat_type || "Thường"})</span>
                          <span className="text-xs text-gray-500 border-l border-gray-700 pl-2">
                            {seat.price ? parseFloat(seat.price).toLocaleString('vi-VN') : 0}đ
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Cột phải: Phương thức thanh toán & Tổng kết */}
            <div className="lg:col-span-5 space-y-6">
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-red-500" />
                  Phương thức thanh toán
                </h3>

                {/* VNPay Gateway Option */}
                <div className="p-4 rounded-xl border-2 border-red-600 bg-red-950/20 relative">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white flex items-center justify-center p-1 font-black text-blue-600 text-xs shadow">
                        VNPAY
                      </div>
                      <div>
                        <h4 className="font-bold text-white text-sm">Cổng thanh toán VNPay Sandbox</h4>
                        <p className="text-xs text-gray-400">ATM, Internet Banking, VNPAY-QR, Thẻ Quốc tế</p>
                      </div>
                    </div>
                    <CheckCircle2 className="w-5 h-5 text-red-500" />
                  </div>
                  <div className="mt-2 text-xs text-gray-400 bg-gray-900/60 p-2.5 rounded-lg border border-gray-800">
                    Thanh toán an toàn, bảo mật qua hệ thống giả lập VNPay Sandbox.
                  </div>
                </div>

                {/* Price Summary */}
                <div className="pt-4 border-t border-gray-800 space-y-2 text-sm">
                  <div className="flex justify-between text-gray-400">
                    <span>Tạm tính ({booking.seats?.length || 1} ghế):</span>
                    <span>{booking.totalAmount ? Number(booking.totalAmount).toLocaleString('vi-VN') : 0} VNĐ</span>
                  </div>
                  <div className="flex justify-between text-gray-400">
                    <span>Phí tiện ích:</span>
                    <span className="text-green-400">Miễn phí</span>
                  </div>
                  <div className="flex justify-between items-center text-base pt-2 border-t border-gray-800 font-bold">
                    <span className="text-white">Tổng cộng:</span>
                    <span className="text-2xl text-red-500 font-extrabold">
                      {booking.totalAmount ? Number(booking.totalAmount).toLocaleString('vi-VN') : 0} VNĐ
                    </span>
                  </div>
                </div>

                {/* Action CTA */}
                <button
                  onClick={handleVNPay}
                  disabled={expired || isRedirecting}
                  className={`w-full py-4 rounded-xl font-bold text-white flex items-center justify-center gap-2 shadow-lg transition-all text-base ${
                    expired || isRedirecting
                      ? "bg-gray-700 cursor-not-allowed opacity-70"
                      : "bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 shadow-red-900/30 hover:shadow-red-900/50 hover:scale-[1.01]"
                  }`}
                >
                  {isRedirecting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Đang kết nối tới VNPay...
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="w-5 h-5" />
                      Thanh toán qua VNPay ({booking.totalAmount ? Number(booking.totalAmount).toLocaleString('vi-VN') : 0}đ)
                    </>
                  )}
                </button>

                <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
                  <ShieldCheck className="w-4 h-4 text-gray-400" />
                  Giao dịch được mã hóa và bảo mật 100%
                </div>
              </div>

              {/* Back button */}
              <button
                onClick={() => navigate(-1)}
                className="w-full py-2.5 text-sm text-gray-400 hover:text-white flex items-center justify-center gap-2 transition"
              >
                <ArrowLeft className="w-4 h-4" />
                Quay lại chọn ghế khác
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PaymentPage;
