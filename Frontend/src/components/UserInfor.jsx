import React, { useState, useEffect } from 'react';
import { User, Calendar, MapPin, Clock, CreditCard, Ticket, Edit3, Save, X, Filter } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';

const UserInfo = () => {
  const navigate = useNavigate();
  const [userInfo, setUserInfo] = useState({
    username: '',
    email: '',
    phone: '',
    full_name: '',
    avatar: ''
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [bookingHistory, setBookingHistory] = useState([]);
  const [filteredBookings, setFilteredBookings] = useState([]);
  const [sortBy, setSortBy] = useState('newest');

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        setLoading(true);
        const userInfoString = localStorage.getItem('userInfo');
        if (!userInfoString) {
          navigate('/loginpage');
          return;
        }
        
        const userInfo1 = JSON.parse(userInfoString);
        if (!userInfo1.access_token) {
          navigate('/loginpage');
          return;
        }

        setUserInfo(userInfo1);
        setFormData(userInfo1);
        console.log('ID người dùng:', userInfo1.id);
        setLoading(false);
      } catch (err) {
        console.error('Lỗi khi lấy thông tin người dùng:', err);
        setError('Không thể lấy thông tin người dùng. Vui lòng đăng nhập lại.');
        setLoading(false);
      }
    };

    const fetchBookingHistory = async () => {
      try {
        const userInfoString = localStorage.getItem('userInfo');
        const userInfo1 = JSON.parse(userInfoString);
        
        if (!userInfo1 || !userInfo1.access_token) {
          return;
        }

        // Sử dụng endpoint đúng: GET /bookings (lấy tất cả bookings của user hiện tại)
        const response = await api.get('/bookings');
        console.log('Lịch sử đặt vé:', response.data);
        setBookingHistory(response.data);
        setFilteredBookings(response.data);
      } catch (err) {
        console.error('Lỗi khi lấy lịch sử đặt vé:', err);
        
        // Xử lý lỗi 401
        if (err.response && err.response.status === 401) {
          alert('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');
          localStorage.removeItem('userInfo');
          navigate('/loginpage');
        }
      }
    };

    fetchUserData();
    fetchBookingHistory();
  }, []);

  // Filter and sort bookings
  useEffect(() => {
    let filtered = [...bookingHistory];
    
    // Sort bookings
    filtered.sort((a, b) => {
      const dateA = new Date(a.bookingDate || a.booking_date || a.showDate || a.show_date || 0);
      const dateB = new Date(b.bookingDate || b.booking_date || b.showDate || b.show_date || 0);
      const amountA = a.totalAmount || a.total_amount || 0;
      const amountB = b.totalAmount || b.total_amount || 0;

      if (sortBy === 'newest') {
        return dateB - dateA;
      } else if (sortBy === 'oldest') {
        return dateA - dateB;
      } else if (sortBy === 'amount_high') {
        return amountB - amountA;
      } else if (sortBy === 'amount_low') {
        return amountA - amountB;
      }
      return 0;
    });
    
    setFilteredBookings(filtered);
  }, [bookingHistory, sortBy]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prevState => ({
      ...prevState,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      setLoading(true);
      const formDataToSend = new FormData();
      Object.keys(formData).forEach(key => {
        if (key !== 'avatar' && key !== 'created_at' && key !== 'role') {
          formDataToSend.append(key, formData[key]);
        }
      });

      const response = await api.put(
        '/user/profile',
        formDataToSend,
      );

      if (response.data.success) {
        setUserInfo(response.data.user);
        localStorage.setItem('userInfo', JSON.stringify(response.data.user));
        setSuccess('Cập nhật thông tin thành công!');
        setIsEditing(false);
      } else {
        throw new Error(response.data.message || 'Cập nhật thông tin thất bại');
      }
      setLoading(false);
    } catch (err) {
      console.error('Lỗi khi cập nhật thông tin:', err);
      setError(err.response?.data?.message || 'Đã có lỗi xảy ra khi cập nhật thông tin.');
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFormData(userInfo);
    setIsEditing(false);
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'confirmed': { bg: 'bg-green-100', text: 'text-green-800', label: 'Đã xác nhận' },
      'pending': { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Chờ xác nhận' },
      'cancelled': { bg: 'bg-red-100', text: 'text-red-800', label: 'Đã hủy' },
      'completed': { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Hoàn thành' }
    };
    
    const config = statusConfig[status] || statusConfig['completed'];
    return (
      <span className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    );
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: 'VND'
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-red-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto px-4 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Thông Tin Tài Khoản
          </h1>
          <p className="text-gray-600">Quản lý thông tin cá nhân và lịch sử đặt vé của bạn</p>
        </div>

        {/* Alerts */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6 rounded-r-lg">
            <div className="flex">
              <div className="flex-shrink-0">
                <X className="h-5 w-5 text-red-400" />
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        {success && (
          <div className="bg-green-50 border-l-4 border-green-400 p-4 mb-6 rounded-r-lg">
            <div className="flex">
              <div className="flex-shrink-0">
                <Save className="h-5 w-5 text-green-400" />
              </div>
              <div className="ml-3">
                <p className="text-sm text-green-700">{success}</p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* User Info Card */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="bg-gradient-to-r from-red-500 to-red-600 px-6 py-8 text-white">
                <div className="flex items-center space-x-4">
                  <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center">
                    <User className="w-8 h-8" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold">{userInfo.full_name || 'Chưa cập nhật'}</h3>
                    <p className="text-red-100">@{userInfo.username}</p>
                  </div>
                </div>
              </div>
              
              <div className="p-6">
                {isEditing ? (
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Họ và tên
                      </label>
                      <input
                        type="text"
                        name="full_name"
                        value={formData.full_name || ''}
                        onChange={handleChange}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Email
                      </label>
                      <input
                        type="email"
                        name="email"
                        value={formData.email || ''}
                        onChange={handleChange}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Số điện thoại
                      </label>
                      <input
                        type="tel"
                        name="phone"
                        value={formData.phone || ''}
                        onChange={handleChange}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      />
                    </div>
                    <div className="flex space-x-3 pt-4">
                      <button
                        type="submit"
                        disabled={loading}
                        className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-lg transition duration-200 flex items-center justify-center space-x-2"
                      >
                        <Save className="w-4 h-4" />
                        <span>Lưu</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleCancel}
                        className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 font-medium py-2 px-4 rounded-lg transition duration-200 flex items-center justify-center space-x-2"
                      >
                        <X className="w-4 h-4" />
                        <span>Hủy</span>
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                      <User className="w-5 h-5 text-gray-500" />
                      <div>
                        <p className="text-sm text-gray-500">Họ và tên</p>
                        <p className="font-medium">{userInfo.full_name || 'Chưa cập nhật'}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                      <CreditCard className="w-5 h-5 text-gray-500" />
                      <div>
                        <p className="text-sm text-gray-500">Email</p>
                        <p className="font-medium">{userInfo.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                      <Calendar className="w-5 h-5 text-gray-500" />
                      <div>
                        <p className="text-sm text-gray-500">Số điện thoại</p>
                        <p className="font-medium">{userInfo.phone || 'Chưa cập nhật'}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setIsEditing(true)}
                      className="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-lg transition duration-200 flex items-center justify-center space-x-2"
                    >
                      <Edit3 className="w-4 h-4" />
                      <span>Chỉnh sửa thông tin</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Booking History */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
                  <div className="flex items-center space-x-3">
                    <Ticket className="w-6 h-6 text-red-600" />
                    <h2 className="text-xl font-bold text-gray-900">Lịch sử đặt vé</h2>
                    <span className="bg-red-100 text-red-800 text-xs font-medium px-2.5 py-0.5 rounded-full">
                      {filteredBookings.length} vé
                    </span>
                  </div>
                  
                  <div>
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                    >
                      <option value="newest">Mới nhất</option>
                      <option value="oldest">Cũ nhất</option>
                      <option value="amount_high">Giá cao nhất</option>
                      <option value="amount_low">Giá thấp nhất</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="p-6">
                {filteredBookings.length === 0 ? (
                  <div className="text-center py-12">
                    <Ticket className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">Chưa có lịch sử đặt vé</h3>
                    <p className="text-gray-500">Bạn chưa đặt vé nào.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {filteredBookings.map((booking) => {
                      const filmTitle = booking.filmTitle || booking.movie_title || booking.film_title || 'N/A';
                      const theaterName = booking.theaterName || booking.theater_name || 'N/A';
                      const roomName = booking.roomName || booking.room_name || 'N/A';
                      const showDate = booking.showDate || booking.show_date;
                      const startTime = booking.startTime || booking.start_time || '';
                      const totalAmount = booking.totalAmount || booking.total_amount || 0;
                      const status = (booking.bookingStatus || booking.booking_status || 'completed').toLowerCase();
                      const seatsStr = Array.isArray(booking.seats)
                        ? booking.seats.map(s => typeof s === 'object' ? (s.seat_name || s.seatName || s.seat_id) : s).join(', ')
                        : (booking.seats || 'N/A');

                      return (
                        <div key={booking.id} className="border border-gray-200 rounded-xl p-6 hover:shadow-md transition-shadow duration-200">
                          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
                            <div className="flex-1 space-y-3">
                              <div className="flex items-start justify-between">
                                <div>
                                  <h3 className="text-lg font-bold text-gray-900 mb-1">
                                    {filmTitle}
                                  </h3>
                                  <p className="text-sm text-gray-500">Mã đặt vé: #{booking.id}</p>
                                </div>
                                {getStatusBadge(status)}
                              </div>
                              
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                <div className="flex items-center space-x-2">
                                  <MapPin className="w-4 h-4 text-gray-400" />
                                  <span className="text-gray-600">
                                    {theaterName} - {roomName}
                                  </span>
                                </div>
                                <div className="flex items-center space-x-2">
                                  <Calendar className="w-4 h-4 text-gray-400" />
                                  <span className="text-gray-600">
                                    {showDate ? formatDate(showDate) : 'N/A'}
                                  </span>
                                </div>
                                <div className="flex items-center space-x-2">
                                  <Clock className="w-4 h-4 text-gray-400" />
                                  <span className="text-gray-600">
                                    {startTime}
                                  </span>
                                </div>
                                <div className="flex items-center space-x-2">
                                  <Ticket className="w-4 h-4 text-gray-400" />
                                  <span className="text-gray-600">
                                    Ghế: {seatsStr}
                                  </span>
                                </div>
                              </div>
                            </div>
                            
                            <div className="flex flex-col items-end space-y-2">
                              <div className="text-right">
                                <p className="text-sm text-gray-500">Tổng tiền</p>
                                <p className="text-2xl font-bold text-red-600">
                                  {formatCurrency(totalAmount)}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserInfo;
