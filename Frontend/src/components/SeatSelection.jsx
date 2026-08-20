import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../config/api';
import { clearSession, getCurrentUser } from '../services/authStorage';

const SeatSelection = () => {
  const { showtimeId } = useParams();
  const navigate = useNavigate();
  const [showtimeInfo, setShowtimeInfo] = useState(null);
  const [seatData, setSeatData] = useState([]);
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dataFetched, setDataFetched] = useState(false);
  // Sử dụng useCallback để tránh tạo hàm mới mỗi lần render
  const fetchData = useCallback(async () => {
    // Nếu đã fetch dữ liệu rồi thì không fetch lại
    if (dataFetched) return;
    try {
      setLoading(true);
      setError(null);
      // Lấy thông tin suất chiếu
      const showtimeResponse = await api.get(`/showtimes/${showtimeId}`);
      console.log("Thông tin suất chiếu:", showtimeResponse.data);
      setShowtimeInfo(showtimeResponse.data);
      // Lấy thông tin ghế
      const seatsResponse = await api.get(`/seats/showtime/${showtimeId}`);
      console.log("Thông tin ghế:", seatsResponse.data);
      setSeatData(seatsResponse.data);
      // Đánh dấu đã fetch dữ liệu
      setDataFetched(true);
    } catch (err) {
      console.error('Lỗi khi tải dữ liệu:', err);
      setError('Không thể tải thông tin. Vui lòng thử lại sau.');
    } finally {
      setLoading(false);
    }
  }, [showtimeId, dataFetched]);
  useEffect(() => {

    fetchData();
  }, [showtimeId, fetchData]);
  const handleSeatClick = async (seat) => {
    const isSelected = selectedSeats.includes(seat.seat_id);
    if (seat.status === 'BOOKED' || (seat.status === 'HOLD' && !isSelected)) return;

    const userInfo = getCurrentUser();
    if (!userInfo || !userInfo.id) {
      navigate('/loginpage', {
        state: {
          redirectTo: `/seat-selection/${showtimeId}`,
          message: 'Vui lòng đăng nhập để đặt vé'
        }
      });
      return;
    }

    if (!userInfo.access_token) {
      alert('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');
      navigate('/loginpage');
      return;
    }

    try {
      if (isSelected) {
        await api.post("/seats/release", {
          showtime_id: parseInt(showtimeId),
          seat_ids: [seat.seat_id],
        });
        setSelectedSeats(prev => prev.filter(id => id !== seat.seat_id));
        setSeatData(prev => prev.map(item => (
          item.seat_id === seat.seat_id
            ? { ...item, status: 'AVAILABLE', hold_by_user_id: null, hold_expired_at: null }
            : item
        )));
        return;
      }

      const holdResponse = await api.post("/seats/hold", {
        showtime_id: parseInt(showtimeId),
        seat_ids: [seat.seat_id],
      });
      const holdInfo = holdResponse.data?.[0];
      setSelectedSeats(prev => (
        prev.includes(seat.seat_id) ? prev : [...prev, seat.seat_id]
      ));
      setSeatData(prev => prev.map(item => (
        item.seat_id === seat.seat_id
          ? {
              ...item,
              status: 'HOLD',
              hold_by_user_id: userInfo.id,
              hold_expired_at: holdInfo?.hold_expired_at || item.hold_expired_at,
            }
          : item
      )));
    } catch (err) {
      console.error('Lỗi khi giữ/hủy ghế:', err);
      alert(err.response?.data?.detail || 'Không thể cập nhật trạng thái ghế. Vui lòng thử lại.');
      const seatsResponse = await api.get(`/seats/showtime/${showtimeId}`);
      setSeatData(seatsResponse.data);
    }
  };
  const calculateTotal = () => {
    return selectedSeats.reduce((total, seatId) => {
      const seat = seatData.find(s => s.seat_id === seatId);
      return total + (seat ? parseFloat(seat.price) : 0);
    }, 0);
  };
  const handleBooking = async () => {
    if (selectedSeats.length === 0) {
      alert('Vui lòng chọn ít nhất một ghế');
      return;
    }
    try {
      // Lấy thông tin người dùng từ localStorage
      const userInfo = getCurrentUser();
      if (!userInfo || !userInfo.id) {
        // Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập
        navigate('/loginpage', { 
          state: { 
            redirectTo: `/seat-selection/${showtimeId}`, 
            message: 'Vui lòng đăng nhập để đặt vé' 
          } 
        });
        return;
      }

      // Kiểm tra có token không
      if (!userInfo.access_token) {
        alert('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');
        navigate('/loginpage');
        return;
      }

      // Tạo dữ liệu đặt vé
      const bookingData = {
        userId: userInfo.id,
        showtimeId: parseInt(showtimeId),
        totalAmount: calculateTotal(),
        paymentMethod: "Online",
        seats: selectedSeats.map((seatId) => {
          const seat = seatData.find((s) => s.seat_id === seatId);
          return { seat_id: seatId, price: seat ? seat.price : 0 };
        }),
      };
      console.log("Dữ liệu gửi lên backend:", bookingData);
      console.log("Token:", userInfo.access_token);

      // Gửi request đặt vé
      const response = await api.post("/bookings", bookingData);
      console.log("Kết quả đặt vé:", response.data);
      navigate(`/payment/${response.data.bookingId}`);
    } catch (err) {
      console.error("Lỗi khi đặt vé:", err);
      
      // Xử lý lỗi 401 - Unauthorized
      if (err.response && err.response.status === 401) {
        alert('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');
        clearSession();
        navigate('/loginpage', {
          state: {
            redirectTo: `/seat-selection/${showtimeId}`,
            message: 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.'
          }
        });
      } else {
        const errorMessage = err.response?.data?.detail || "Đã xảy ra lỗi khi đặt vé. Vui lòng thử lại.";
        alert(errorMessage);
      }
    }
  };
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: 'Asia/Ho_Chi_Minh'
    });
  };
  // Hàm định dạng giờ
const formatTime = (timeString) => {
  if (timeString && timeString.includes(':')) {
    const [hours, minutes] = timeString.split(':');
    return `${hours}:${minutes}`;
  }
  return timeString;
};
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-red-600"></div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-6 rounded-lg shadow-md max-w-md w-full">
          <h2 className="text-xl font-bold text-red-600 mb-4">Lỗi</h2>
          <p className="text-gray-700">{error}</p>
          <button 
            className="mt-4 w-full bg-red-600 text-white py-2 rounded-lg hover:bg-red-700"
            onClick={() => navigate(-1)}
          >
            Quay lại
          </button>
        </div>
      </div>
    );
  }
  // Tạo mảng chứa các hàng ghế
  const rows = [...new Set(seatData.map(seat => seat.seat_name?.charAt(0)))].filter(Boolean).sort();
  // Nhóm ghế theo hàng
  const seatsByRow = {};
  rows.forEach(row => {
    seatsByRow[row] = seatData
      .filter(seat => seat.seat_name.charAt(0) === row)
      .sort((a, b) => {
        const numA = parseInt(a.seat_name.substring(1));
        const numB = parseInt(b.seat_name.substring(1));
        return numA - numB;
      });
  });
  return (
    <div className="min-h-screen bg-gray-100 py-8">
      <div className="container mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Đặt vé xem phim</h1>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            {/* Thông tin phim */}
            {showtimeInfo && (
              <div className="bg-white rounded-lg shadow-md p-4 mb-6">
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="w-full md:w-1/4">
                    {showtimeInfo.image && (
                      <img 
                        src={showtimeInfo.image} 
                        alt={showtimeInfo.film_title} 
                        className="w-full h-64 object-cover rounded-lg"
                        
                      />
                    )}
                  </div>
                  <div className="w-full md:w-3/4">
                    <h2 className="text-2xl font-bold text-gray-800 mb-2">{showtimeInfo.film_title}</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-gray-600">
                      <div>
                        <p><span className="font-semibold">Rạp:</span> {showtimeInfo.theater_name}</p>
                        <p><span className="font-semibold">Phòng:</span> {showtimeInfo.room_name}</p>
                        <p><span className="font-semibold">Loại phòng:</span> {showtimeInfo.format}</p>
                      </div>
                      <div>
                      <p><span className="font-semibold">Ngày chiếu:</span> {formatDate(showtimeInfo.show_date)}</p>
<p><span className="font-semibold">Giờ chiếu:</span> {formatTime(showtimeInfo.start_time, showtimeInfo.show_date)}</p>

                        <p><span className="font-semibold">Thời lượng:</span> {showtimeInfo.duration}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Sơ đồ ghế */}
            <div className="bg-white rounded-lg shadow-md p-4 mb-6">
              <div className="w-full bg-gray-800 text-white py-2 text-center rounded-t-lg mb-6">
                Màn hình
              </div>
              
              <div className="flex flex-col items-center space-y-2">
                {rows.map(row => (
                  <div key={row} className="flex items-center w-full">
                    <div className="w-8 text-center font-bold">{row}</div>
                    <div className="flex flex-1 justify-center gap-2">
                      {seatsByRow[row].map(seat => {
                        const isBooked = seat.status === 'BOOKED';
                        const isSelected = selectedSeats.includes(seat.seat_id);
                        const isHold = seat.status === 'HOLD' && !isSelected;
                        const isAvailable = seat.status === 'AVAILABLE';
                        
                        // Xác định màu sắc theo loại ghế (case-insensitive)
                        const seatType = seat.seat_type?.toLowerCase();
                        let bgColor = '';
                        if (isBooked || isHold) {
                          bgColor = 'bg-gray-500 cursor-not-allowed';
                        } else if (isSelected) {
                          bgColor = 'bg-green-500 text-white';
                        } else if (isAvailable) {
                          if (seatType === 'vip' || seatType === 'premium') {
                            bgColor = 'bg-red-200 hover:bg-red-300';
                          } else if (seatType === 'couple') {
                            bgColor = 'bg-pink-200 hover:bg-pink-300';
                          } else {
                            bgColor = 'bg-blue-200 hover:bg-blue-300';
                          }
                        }
                        
                        return (
                          <button
                            key={seat.seat_id}
                            className={`w-8 h-8 rounded-t-lg text-xs font-bold flex items-center justify-center transition-colors ${bgColor}`}
                            onClick={() => handleSeatClick(seat)}
                            disabled={isBooked || isHold}
                            title={`${seat.seat_name} - ${seat.seat_type} - ${seat.price.toLocaleString()}đ - ${seat.status}`}
                          >
                            {seat.seat_name.substring(1)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="flex justify-center mt-6 gap-4 flex-wrap">
                <div className="flex items-center">
                  <div className="w-4 h-4 bg-blue-200 rounded-sm mr-2"></div>
                  <span className="text-sm">Ghế thường</span>
                </div>
                <div className="flex items-center">
                  <div className="w-4 h-4 bg-red-200 rounded-sm mr-2"></div>
                  <span className="text-sm">Ghế VIP</span>
                </div>
                <div className="flex items-center">
                  <div className="w-4 h-4 bg-pink-200 rounded-sm mr-2"></div>
                  <span className="text-sm">Ghế đôi</span>
                </div>
                <div className="flex items-center">
                  <div className="w-4 h-4 bg-green-500 rounded-sm mr-2"></div>
                  <span className="text-sm">Đã chọn</span>
                </div>
                <div className="flex items-center">
                  <div className="w-4 h-4 bg-gray-500 rounded-sm mr-2"></div>
                  <span className="text-sm">Đã đặt/Đang giữ</span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Thông tin đặt vé */}
          <div>
            <div className="bg-white rounded-lg shadow-md p-4 sticky top-4">
              <h3 className="text-xl font-bold text-gray-800 mb-4">Thông tin đặt vé</h3>
              
              <div className="mb-4">
                <h4 className="font-semibold text-gray-700 mb-2">Ghế đã chọn:</h4>
                {selectedSeats.length > 0 ? (
                  <div className="space-y-2">
                    {selectedSeats.map(seatId => {
                      const seat = seatData.find(s => s.seat_id === seatId);
                      if (!seat) return null;
                      
                      const seatType = seat.seat_type?.toLowerCase();
                      let typeName = 'Thường';
                      if (seatType === 'vip' || seatType === 'premium') {
                        typeName = 'VIP';
                      } else if (seatType === 'couple') {
                        typeName = 'Đôi';
                      }
                      
                      return (
                        <div key={seat.seat_id} className="flex justify-between items-center">
                          <span>
                            Ghế {seat.seat_name} ({typeName})
                          </span>
                          <span className="font-medium">{parseFloat(seat.price).toLocaleString()}đ</span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-gray-500">Chưa chọn ghế nào</p>
                )}
              </div>
              <div className="border-t pt-4">
                <div className="flex justify-between items-center font-bold text-lg">
                  <span>Tổng tiền:</span>
                  <span className="text-red-600">{calculateTotal().toLocaleString()}đ</span>
                </div>
              </div>
              <button
                className={`w-full mt-4 py-3 rounded-lg font-bold text-white ${
                  selectedSeats.length > 0 
                    ? 'bg-red-600 hover:bg-red-700' 
                    : 'bg-gray-400 cursor-not-allowed'
                }`}
                onClick={handleBooking}
                disabled={selectedSeats.length === 0}
              >
                Đặt vé
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
export default SeatSelection;
