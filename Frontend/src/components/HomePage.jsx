import React, { useState, useEffect } from "react";
import { Link, Outlet } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { AUTH_SESSION_CHANGED_EVENT, clearSession, getAccessToken, getCurrentUser } from "../services/authStorage";


const HomePage = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userInfo, setUserInfo] = useState(null);
  const navigate = useNavigate();
  const handleLogin = () => {
    navigate("/LoginPage");
  };
  const handleHomePage = () => {
    navigate("/");
  };
  const handleUserInfo = () => {
    navigate("/userInfo");
  };
  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  useEffect(() => {
    // Hàm kiểm tra và cập nhật trạng thái đăng nhập
    const checkLoginStatus = () => {
      const currentUser = getCurrentUser();
      const token = getAccessToken();

      if (currentUser && token) {
        setIsLoggedIn(true);
        setUserInfo(currentUser);
      } else {
        setIsLoggedIn(false);
        setUserInfo(null);
      }
    };

    // Kiểm tra khi component mount
    checkLoginStatus();

    // Lắng nghe sự kiện storage để cập nhật khi localStorage thay đổi
    window.addEventListener('storage', checkLoginStatus);

    // Lắng nghe sự kiện custom để cập nhật khi login/logout trong cùng tab
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, checkLoginStatus);

    return () => {
      window.removeEventListener('storage', checkLoginStatus);
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, checkLoginStatus);
    };
  }, []);
  const handleLogout = () => {
    setIsLoggedIn(false);
    setUserInfo(null);
    clearSession();
    
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-gray-900 text-white">
        <div className="container mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center">
              <img
                src="https://gigamall.vn/data/2019/05/06/11365490_logo-cgv-500x500.jpg"
                alt="CGV Logo"
                className="w-10 h-auto mx-auto rounded-lg cursor-pointer"
                onClick={handleHomePage}
              ></img>
              <span
                className="ml-2 text-2xl font-bold cursor-pointer "
                onClick={handleHomePage}
              >
                CGV
              </span>
            </div>

            {/* Mobile menu button */}
            <div className="md:hidden">
              <button
                onClick={toggleMenu}
                className="text-gray-200 hover:text-white focus:outline-none"
              >
                <svg
                  className="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  {isMenuOpen ? (
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  ) : (
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 6h16M4 12h16m-7 6h7"
                    />
                  )}
                </svg>
              </button>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex space-x-8">
              <Link to="/" className="text-gray-300 hover:text-red-500">Trang chủ</Link>
              <Link to="/movie" className="text-gray-300 hover:text-red-500">Phim</Link> 
              <Link to="/cinema" className="text-gray-300 hover:text-red-500">Rạp chiếu</Link>
              <Link to="/contact" className="text-gray-300 hover:text-red-500">Liên hệ</Link>
              <Link to="/about" className="text-gray-300 hover:text-red-500">Về chúng tôi </Link>
            </nav>
            <div className="hidden md:flex items-center space-x-4">
              {isLoggedIn && userInfo ? (
                <div className="flex items-center space-x-4">
                  <div className="text-white cursor-pointer hover:text-red-500" onClick={handleUserInfo}>
                    <span className="font-medium">
                      Xin chào, {userInfo.full_name}
                    </span>
                    <p className="text-xs text-gray-300 hover:text-red-500" >Xem thông tin cá nhân</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-white font-medium"
                  >
                    Đăng xuất
                  </button>
                </div>
              ) : isLoggedIn ? (
                <div className="flex items-center space-x-4">
                  <div className="text-white">
                    <span className="font-medium">Đang tải thông tin...</span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-white font-medium"
                  >
                    Đăng xuất
                  </button>
                </div>
              ) : (
                <button
                  className="border border-red-600 px-4 py-2 rounded text-red-600 hover:bg-red-600 hover:text-white font-medium transition-colors"
                  onClick={handleLogin}
                >
                  Đăng nhập
                </button>
              )}
            </div>
          </div>
          {/* Mobile Navigation */}
          {isMenuOpen && (
            <nav className="mt-4 pt-4 border-t border-gray-700 md:hidden">
              <ul className="space-y-3">
                <div>
                  <Link to="/" className="text-gray-300 hover:text-red-500">Trang chủ</Link>
                  </div>
                <div>
                  <Link to="/movie" className="text-gray-300 hover:text-red-500">Phim</Link> 
                </div>
                <div>
                  <Link to="/cinema" className="text-gray-300 hover:text-red-500">Rạp chiếu</Link>
                </div>
                <div>
                 <Link to="/promotion" className="text-gray-300 hover:text-red-500">Khuyến mãi</Link>
                </div>
                <div>
                  <Link to="/contact" className="text-gray-300 hover:text-red-500">Liên hệ</Link>
                </div>
                <div>
                  <Link to="/about" className="text-gray-300 hover:text-red-500">Về chúng tôi </Link>
                </div>
                <div className=" items-center space-x-4">
              {isLoggedIn && userInfo ? (
                <div className="flex items-center space-x-4">
                  <div className="text-white cursor-pointer hover:text-red-500" onClick={handleUserInfo}>
                    <span className="font-medium">
                      Xin chào, {userInfo.full_name}
                    </span>
                    <p className="text-xs text-gray-300 hover:text-red-500" >Xem thông tin cá nhân</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-white font-medium"
                  >
                    Đăng xuất
                  </button>
                </div>
              ) : isLoggedIn ? (
                <div className="flex items-center space-x-4">
                  <div className="text-white">
                    <span className="font-medium">Đang tải thông tin...</span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-white font-medium"
                  >
                    Đăng xuất
                  </button>
                </div>
              ) : (
                <button
                  className="border border-red-600 px-4 py-2 rounded text-red-600 hover:bg-red-600 hover:text-white font-medium transition-colors"
                  onClick={handleLogin}
                >
                  Đăng nhập
                </button>
              )}
            </div>
              </ul>
            </nav>
            
          )}
     
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      {/* Footer */}
      <footer className="bg-gray-900 text-white py-10">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <h4 className="text-lg font-bold mb-4">CGV Việt Nam</h4>
              <p className="text-gray-400 mb-2">Giới thiệu</p>
              <p className="text-gray-400 mb-2">Tiện ích Online</p>
              <p className="text-gray-400 mb-2">Thẻ quà tặng</p>
              <p className="text-gray-400 mb-2">Tuyển dụng</p>
              <p className="text-gray-400">Liên hệ quảng cáo</p>
            </div>
            <div>
              <h4 className="text-lg font-bold mb-4">Điều khoản sử dụng</h4>
              <p className="text-gray-400 mb-2">Điều khoản chung</p>
              <p className="text-gray-400 mb-2">Điều khoản giao dịch</p>
              <p className="text-gray-400 mb-2">Chính sách thanh toán</p>
              <p className="text-gray-400 mb-2">Chính sách bảo mật</p>
              <p className="text-gray-400">Câu hỏi thường gặp</p>
            </div>
            <div>
              <h4 className="text-lg font-bold mb-4">Kết nối với CGV</h4>
              <div className="flex space-x-4 mb-4">
                <a href="#" className="text-white hover:text-red-500">
                  <svg
                    className="h-6 w-6"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z" />
                  </svg>
                </a>
                <a href="#" className="text-white hover:text-red-500">
                  <svg
                    className="h-6 w-6"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
                  </svg>
                </a>
                <a href="#" className="text-white hover:text-red-500">
                  <svg
                    className="h-6 w-6"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84" />
                  </svg>
                </a>
              </div>
              <p className="text-gray-400">Hotline: 1900 6017</p>
              <p className="text-gray-400">Email: hoidap@cgv.vn</p>
            </div>
            <div>
              <h4 className="text-lg font-bold mb-4">Chăm sóc khách hàng</h4>
              <img
                src="https://www.cgv.vn/skin/frontend/cgv/default/images/cgvlogo.png"
                alt="CGV Logo"
                className="h-10 mb-4"
              />
              <p className="text-gray-400">Tầng 2, Rivera Park Saigon</p>
              <p className="text-gray-400">
                7/28 Thành Thái, P.14, Q.10, TPHCM
              </p>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>© 2025 CJ CGV. Tất cả các quyền được bảo lưu.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};
export default HomePage;
