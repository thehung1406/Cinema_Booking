import React, { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { useParams, useNavigate } from "react-router-dom";

const PaymentPage = () => {
  const { bookingId } = useParams();
  const navigate = useNavigate();
  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expired, setExpired] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(600);

  // Clean bookingId - chỉ tính 1 lần với useMemo
  const cleanBookingId = useMemo(() => {
    const cleaned = bookingId ? bookingId.split(':')[0] : null;
    console.log('Cleaned bookingId:', cleaned);
    return cleaned;
  }, [bookingId]);

  // Tạo axios instance - chỉ tạo 1 lần với useMemo
  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: '/api'
    });

    instance.interceptors.request.use(
      (config) => {
        const userInfo = JSON.parse(localStorage.getItem('userInfo'));
        if (userInfo && userInfo.access_token) {
          config.headers.Authorization = `Bearer ${userInfo.access_token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    return instance;
  }, []);

  // Lấy thông tin booking từ API
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Validate bookingId
        if (!cleanBookingId || isNaN(cleanBookingId)) {
          setError('ID đặt vé không hợp lệ');
          setLoading(false);
          return;
        }

        // Kiểm tra đăng nhập
        const userInfo = JSON.parse(localStorage.getItem('userInfo'));
        if (!userInfo || !userInfo.access_token) {
          navigate('/loginpage');
          return;
        }

        const response = await api.get(`/bookings/${cleanBookingId}`);
        setBooking(response.data);
        setLoading(false);
      } catch (error) {
        console.error("Lỗi khi lấy thông tin booking:", error);
        
        // Xử lý lỗi 401
        if (error.response && error.response.status === 401) {
          alert('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');
          localStorage.removeItem('userInfo');
          navigate('/loginpage');
        } else if (error.response && error.response.status === 404) {
          setError("Không tìm thấy thông tin đặt vé.");
        } else if (error.response && error.response.status === 405) {
          setError("Phương thức request không được hỗ trợ. Vui lòng kiểm tra lại.");
        } else {
          setError("Không thể lấy thông tin đặt vé. Vui lòng thử lại sau.");
        }
        setLoading(false);
      }
    };
    fetchData();
  }, [cleanBookingId, navigate]); // Thêm dependencies đầy đủ

  // Đếm ngược 10 phút kể từ bookingDate

  useEffect(() => {
    if (!booking || !booking.bookingDate) return;
    
    // Parse booking date - backend trả về UTC time nhưng thiếu 'Z'
    // Phải thêm 'Z' để JavaScript hiểu đúng là UTC
    let bookingDateStr = booking.bookingDate;
    if (!bookingDateStr.endsWith('Z') && !bookingDateStr.includes('+')) {
      bookingDateStr = bookingDateStr + 'Z';
    }
    
    const bookingTime = new Date(bookingDateStr).getTime();
    
    // Kiểm tra nếu bookingTime không hợp lệ
    if (isNaN(bookingTime)) {
      console.error('Invalid booking date:', booking.bookingDate);
      return;
    }
    
    const expireTime = bookingTime + 10 * 60 * 1000; // 10 phút sau booking time
    
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
      api.patch(`/bookings/${cleanBookingId}/payment-status?payment_status=FAILED`);
    }
  }, [expired, booking, cleanBookingId, api]);

  const handleVNPay = async () => {
    if (!booking) return;
    try {
      const res = await axios.post(`/api/payment/vnpay-url`, {
        bookingId: booking.id,
        amount: booking.totalAmount,
        orderInfo: `Thanh toán vé phim #${booking.id}`,
        returnUrl: `${window.location.origin}/payment-result`  // Đổi URL
      });
      window.location.href = res.data.paymentUrl;
    } catch (err) {
      console.error("Lỗi thanh toán:", err);
      alert("Không thể kết nối đến cổng thanh toán.");
    }
  };

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  };

  if (loading) return <div className="text-center py-10">Đang tải...</div>;
  if (error) return <div className="text-red-500 text-center py-10">{error}</div>;
  if (!booking) return <div className="text-center py-10">Không tìm thấy thông tin đặt vé.</div>;

  return (
    <div className="max-w-lg mx-auto mt-10 p-6 bg-white shadow-lg rounded-lg">
      <h2 className="text-2xl font-bold mb-4 text-center">Thanh toán vé phim</h2>
      {expired ? (
        <div className="text-center text-red-600 font-bold text-lg">
          Đã hết thời gian thanh toán! Đơn hàng đã bị hủy.
        </div>
      ) : (
        <>
          {/* Bộ đếm thời gian nổi bật */}
          <div className="mb-6 p-4 bg-red-50 border-2 border-red-500 rounded-lg">
            <div className="text-center">
              <p className="text-sm text-gray-700 mb-2">Thời gian còn lại để thanh toán</p>
              <div className="text-4xl font-bold text-red-600 font-mono">
                {formatTime(secondsLeft)}
              </div>
              <p className="text-xs text-gray-600 mt-2">Vui lòng hoàn tất thanh toán trước khi hết giờ</p>
            </div>
          </div>

          <div className="mb-4 flex flex-col gap-3">
            {booking.filmImage && (
              <img
                src={booking.filmImage}
                alt={booking.filmTitle || 'Poster phim'}
                className="w-full h-64 object-cover rounded-lg"
                onError={(e) => {
                  e.target.style.display = 'none';
                  console.log('Image load failed:', booking.filmImage);
                }}
              />
            )}

            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Mã đơn hàng:</span>{' '}
              <span className="text-gray-900">{booking.id || 'N/A'}</span>
            </div>
            
            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Phim:</span>{' '}
              <span className="text-gray-900">{booking.filmTitle || 'N/A'}</span>
            </div>
            
            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Rạp:</span>{' '}
              <span className="text-gray-900">{booking.theaterName || 'N/A'}</span>
            </div>
            
            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Phòng:</span>{' '}
              <span className="text-gray-900">{booking.roomName || 'N/A'}</span>
            </div>
            
            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Suất chiếu:</span>{' '}
              <span className="text-gray-900">
                {booking.showDate && booking.showDate !== 'None' 
                  ? new Date(booking.showDate).toLocaleDateString('vi-VN')
                  : 'N/A'}{' '}
                {booking.startTime && booking.startTime !== 'None' 
                  ? booking.startTime.substring(0, 5)
                  : ''}
              </span>
            </div>
            
            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Ghế:</span>{' '}
              <span className="text-gray-900">
                {booking.seats && booking.seats.length > 0
                  ? booking.seats.map(seat => seat.seat_name).join(', ')
                  : 'N/A'}
              </span>
            </div>
            
            <div className="border-b pb-2">
              <span className="font-semibold text-gray-700">Khách hàng:</span>{' '}
              <span className="text-gray-900">{booking.fullName || 'N/A'}</span>
            </div>
            
            <div className="pt-2">
              <span className="font-semibold text-gray-700">Tổng tiền:</span>{' '}
              <span className="text-red-600 font-bold text-xl">
                {booking.totalAmount 
                  ? booking.totalAmount.toLocaleString('vi-VN')
                  : '0'} VNĐ
              </span>
            </div>
          </div>
          
          <div className="flex flex-col items-center gap-2 mt-6">
            <button
              className="w-full px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-semibold text-lg"
              onClick={handleVNPay}
              disabled={expired}
            >
              Thanh toán qua VNPay
            </button>
            <p className="text-xs text-gray-500 text-center">
              Bạn sẽ được chuyển đến cổng thanh toán VNPay
            </p>
          </div>
        </>
      )}
    </div>
  );
};

export default PaymentPage;
