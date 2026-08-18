import React, { useEffect, useState } from "react";
import { QRCode } from 'react-qr-code';
import { useNavigate } from "react-router-dom";
import api from "../config/api";


import { useLocation } from "react-router-dom";

const VnpayReturn = () => {
  const navigate = useNavigate();

  const location = useLocation();
  const [booking, setBooking] = useState(null);
  const [status, setStatus] = useState("pending");
  const [error, setError] = useState(null);

  // Lấy params từ URL
  const params = new URLSearchParams(location.search);
  const vnp_ResponseCode = params.get("vnp_ResponseCode");
  const vnp_TxnRef = params.get("vnp_TxnRef"); // bookingId

  // Xác nhận và cập nhật trạng thái booking/ghế
  useEffect(() => {
    const updateBookingStatus = async () => {
      if (!vnp_TxnRef) return;
      try {
        // Gọi API backend để xác nhận/cập nhật trạng thái booking và ghế
        const res = await api.post("/payment/vnpay-return", {
          bookingId: vnp_TxnRef,
          vnp_ResponseCode,
        });
        setBooking(res.data.booking);
        setStatus(res.data.status);
      } catch (err) {
        setError("Không thể xác nhận giao dịch. Vui lòng liên hệ hỗ trợ.", err);
        setStatus("error");
      }
    };
    if (vnp_ResponseCode) updateBookingStatus();
  }, [vnp_TxnRef, vnp_ResponseCode]);

  // Hiển thị thông tin
  if (status === "pending") return <div className="text-center py-10">Đang xác nhận giao dịch...</div>;
  if (status === "error") return <div className="text-red-500 text-center py-10">{error}</div>;

  return (
    <div className="max-w-xl mx-auto mt-10 p-6 bg-white shadow-lg rounded-lg">
      <h2 className="text-2xl font-bold mb-4 text-center">
        {vnp_ResponseCode === "00" ? "Thanh toán thành công!" : "Thanh toán thất bại"}
      </h2>
      {vnp_ResponseCode === "00" && booking ? (
        <>
          <div className="mb-4 flex flex-col gap-2">
            <div><span className="font-semibold">Mã đơn hàng:</span> {booking.id}</div>
            <div><span className="font-semibold">Phim:</span> {booking.filmTitle || booking.film_title || '--'}</div>
            <div><span className="font-semibold">Rạp:</span> {booking.theaterName || booking.theater_name || '--'}</div>
            <div><span className="font-semibold">Phòng:</span> {booking.roomName || booking.room_name || '--'}</div>
            <div><span className="font-semibold">Suất chiếu:</span> {booking.showDate ? new Date(booking.showDate).toLocaleDateString('vi-VN') : '--'} {booking.startTime || booking.start_time || ''}</div>
            <div><span className="font-semibold">Ghế:</span> {booking.seats?.map(seat => seat.seat_name || seat.seatName).join(', ')}</div>
            <div><span className="font-semibold">Tổng tiền:</span> <span className="text-red-600 font-bold">{booking.totalAmount?.toLocaleString('vi-VN') || booking.total_amount?.toLocaleString('vi-VN') || 0} VND</span></div>
          </div>
          <div className="flex flex-col items-center gap-2 mt-6">
            <span className="font-semibold mb-2">Quét mã QR để kiểm tra vé:</span>
            <QRCode
              value={JSON.stringify({
                bookingId: booking.id,
                film: booking.filmTitle || booking.film_title,
                seats: booking.seats?.map(seat => seat.seat_name || seat.seatName).join(', '),
                showtime: `${booking.showDate || booking.show_date} ${booking.startTime || booking.start_time}`,
              })}
              size={180}
              level="H"
              includeMargin
            />
          </div>
        </>
      ) : (
        <div className="text-center text-red-600 font-bold text-lg">
          Giao dịch thất bại. Vui lòng thử lại hoặc liên hệ hỗ trợ.
        </div>
      )}
      {booking && (
  <div className="flex flex-col items-center">
    <button
      onClick={() => navigate("/")}
      className="mt-6 px-6 py-2.5 bg-red-500 text-white font-medium text-sm rounded shadow-md hover:bg-red-600 hover:shadow-lg focus:bg-red-700 focus:shadow-lg focus:outline-none focus:ring-0 active:bg-blue-800 active:shadow-lg transition duration-150 ease-in-out"
    >
      Về trang chủ
    </button>
  </div>
)}

    </div>
  );
};

export default VnpayReturn;
