import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { LogOut, Menu, UserRound, X } from "lucide-react";
import {
  AUTH_SESSION_CHANGED_EVENT,
  clearSession,
  getAccessToken,
  getCurrentUser,
} from "../services/authStorage";
import { Button } from "./ui/Primitives";

const links = [
  ["/", "Trang chủ"],
  ["/movie", "Phim"],
  ["/cinema", "Rạp chiếu"],
  ["/contact", "Liên hệ"],
  ["/about", "Về CGV"],
];
export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [user, setUser] = useState(() =>
    getAccessToken() ? getCurrentUser() : null,
  );
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const sync = () => setUser(getAccessToken() ? getCurrentUser() : null);
    window.addEventListener("storage", sync);
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, sync);
    };
  }, []);
  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname, location.search]);
  const account = user ? (
    <>
      <Link to="/userInfo" className="account-link">
        <UserRound size={20} aria-hidden="true" />
        <span>{user.full_name || user.username}</span>
      </Link>
      <button
        aria-label="Đăng xuất"
        title="Đăng xuất"
        className="btn text-gray-300"
        onClick={() => {
          clearSession();
          navigate("/");
        }}
      >
        <LogOut size={20} aria-hidden="true" />
      </button>
    </>
  ) : (
    <Button to="/LoginPage">Đăng nhập</Button>
  );
  const navigation = links.map(([to, label]) => (
    <NavLink
      key={to}
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `nav-link ${isActive || (to === "/movie" && /^\/(movies|MovieDetail|movie\/)/i.test(location.pathname)) ? "active" : ""}`
      }
    >
      {label}
    </NavLink>
  ));
  return (
    <div className="min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 btn btn-primary"
      >
        Đến nội dung chính
      </a>
      <header className="site-header">
        <div className="shell">
          <div className="header-row">
            <Link to="/" aria-label="CGV — Trang chủ" className="brand">
              CGV
              <span className="block text-[9px] tracking-[.2em] text-gray-300 mt-1">
                CINEMA BOOKING
              </span>
            </Link>
            <nav aria-label="Điều hướng chính" className="desktop-nav">
              {navigation}
            </nav>
            <div className="desktop-account flex items-center gap-3">
              {account}
            </div>
            <button
              className="mobile-toggle btn"
              aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
              aria-expanded={menuOpen}
              aria-controls="mobile-navigation"
              onClick={() => setMenuOpen((v) => !v)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setMenuOpen(false);
              }}
            >
              {menuOpen ? <X /> : <Menu />}
            </button>
          </div>
          {menuOpen && (
            <nav
              id="mobile-navigation"
              aria-label="Điều hướng trên điện thoại"
              className="mobile-nav"
            >
              {navigation}
              <div className="flex items-center justify-between border-t border-gray-700 pt-3 mt-2">
                {account}
              </div>
            </nav>
          )}
          {["ADMIN", "STAFF"].includes(user?.role) && (
            <Link
              to="/review-moderation"
              className="block text-sm text-gray-300 pb-3"
            >
              Duyệt đánh giá phim →
            </Link>
          )}
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="shell">
          <div className="grid gap-8 sm:grid-cols-3">
            <div>
              <Link to="/" className="brand">
                CGV
              </Link>
              <p className="text-sm mt-4 max-w-xs leading-6">
                Chọn bộ phim yêu thích, tìm lịch chiếu và đặt ghế cho trải
                nghiệm điện ảnh của bạn.
              </p>
            </div>
            <div>
              <h2 className="font-bold text-white mb-3">Khám phá</h2>
              <div className="flex flex-col items-start gap-2 text-sm">
                <Link className="py-2" to="/movie">
                  Phim & lịch chiếu
                </Link>
                <Link className="py-2" to="/cinema">
                  Hệ thống rạp
                </Link>
                <Link className="py-2" to="/about">
                  Về CGV
                </Link>
              </div>
            </div>
            <div>
              <h2 className="font-bold text-white mb-3">Hỗ trợ khách hàng</h2>
              <p className="text-sm mb-3">
                Hotline: <a href="tel:19006017">1900 6017</a>
              </p>
              <a className="text-sm" href="mailto:hoidap@cgv.vn">
                hoidap@cgv.vn
              </a>
              <Link className="block py-3 text-sm" to="/contact">
                Liên hệ hỗ trợ →
              </Link>
            </div>
          </div>
          <p className="text-xs border-t border-gray-700 mt-8 pt-5">
            © {new Date().getFullYear()} CGV Cinema Booking.
          </p>
        </div>
      </footer>
    </div>
  );
}
