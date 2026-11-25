import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowUpRight, LogOut, Menu, UserRound, X } from "lucide-react";
import { AUTH_SESSION_CHANGED_EVENT, clearSession, getAccessToken, getCurrentUser } from "../services/authStorage";
import { Button } from "./ui/Primitives";

const links = [["/movie", "Phim"], ["/cinema", "Rạp chiếu"], ["/about", "Về CGV"], ["/contact", "Hỗ trợ"]];
export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [user, setUser] = useState(() => getAccessToken() ? getCurrentUser() : null);
  const menu = useRef(null);
  const menuToggle = useRef(null);
  const closeMenu = () => { menu.current?.close(); setMenuOpen(false); menuToggle.current?.focus(); };
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const sync = () => setUser(getAccessToken() ? getCurrentUser() : null);
    window.addEventListener("storage", sync);
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, sync);
    return () => { window.removeEventListener("storage", sync); window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, sync); };
  }, []);
  useEffect(() => { setMenuOpen(false); window.scrollTo(0, 0); }, [location.pathname, location.search]);
  useEffect(() => {
    const dialog = menu.current;
    if (!dialog) return;
    dialog.showModal();
    return () => dialog.close();
  }, [menuOpen]);
  const navigation = links.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive || (to === "/movie" && /^\/(movies|MovieDetail|movie\/)/i.test(location.pathname)) ? "active" : ""}`}>{label}</NavLink>);
  const account = user ? <>
    <Link to="/userInfo" className="account-link"><UserRound size={19} aria-hidden="true" /><span>{user.full_name || user.username}</span></Link>
    <button aria-label="Đăng xuất" title="Đăng xuất" className="btn btn-icon" onClick={() => { clearSession(); navigate("/"); }}><LogOut size={18} aria-hidden="true" /></button>
  </> : <Link to="/LoginPage" className="account-link"><UserRound size={19} aria-hidden="true" /><span>Đăng nhập</span></Link>;
  const staffLinks = <>
    {["ADMIN", "MANAGER", "STAFF"].includes(user?.role) && <Link to="/admin" className="staff-link">Quản trị rạp chiếu <ArrowUpRight size={16} /></Link>}
  </>;
  return <div className="site-app">
    <a href="#main-content" className="skip-link">Đến nội dung chính</a>
    <header className="site-header"><div className="shell header-row">
      <Link to="/" aria-label="CGV — Trang chủ" className="brand">CGV<span>Cinema booking</span></Link>
      <nav aria-label="Điều hướng chính" className="desktop-nav">{navigation}</nav>
      <Button to="/ticket-booking" className="header-book">Đặt vé <ArrowUpRight size={16} /></Button>
      <div className="desktop-account">{account}</div>
      <button ref={menuToggle} className="mobile-toggle btn btn-icon" aria-label="Mở menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(true)}><Menu /></button>
    </div><div className="shell staff-links">{staffLinks}</div></header>
    {menuOpen && <dialog ref={menu} className="mobile-menu" aria-label="Điều hướng trên điện thoại" onCancel={e => { e.preventDefault(); closeMenu(); }} onClose={() => setMenuOpen(false)}>
      <div className="mobile-menu-head"><Link to="/" className="brand">CGV</Link><button autoFocus className="btn btn-icon" aria-label="Đóng menu" onClick={closeMenu}><X /></button></div>
      <nav id="mobile-navigation" onClick={e => { if (e.target.closest("a")) closeMenu(); }} className="mobile-nav" aria-label="Điều hướng trên điện thoại">{navigation}<Button to="/ticket-booking">Đặt vé</Button><div className="mobile-account">{account}</div>{staffLinks}</nav>
    </dialog>}
    <main key={location.pathname} id="main-content" className="user-main" tabIndex={-1}><Outlet /></main>
    <footer className="site-footer"><div className="shell">
      <div className="footer-top"><Link to="/" className="brand">CGV<span>Cinema booking</span></Link><p>Phim bạn muốn xem.<br />Buổi hẹn bạn mong chờ.</p><Button to="/movie" variant="secondary">Xem phim tại rạp <ArrowUpRight size={18} /></Button></div>
      <div className="footer-bottom"><span>© {new Date().getFullYear()} CGV Cinema Booking.</span><nav aria-label="Liên kết cuối trang"><Link to="/movie">Phim & lịch chiếu</Link><Link to="/cinema">Hệ thống rạp</Link><Link to="/contact">Liên hệ hỗ trợ</Link></nav></div>
    </div></footer>
  </div>;
}
