import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Film, Armchair, CalendarDays, Tags, Users, BookOpen, ChartColumn, Shield, ArrowLeft, LogOut } from "lucide-react";
import api from "../../config/api";
import { AUTH_SESSION_CHANGED_EVENT, clearSession, getAccessToken } from "../../services/authStorage";
import "./admin.css";

const sections = [
  ["films", "Phim", "films.manage", <Film size={19} aria-hidden="true" />],
  ["rooms", "Phòng chiếu & ghế", "rooms.manage", <Armchair size={19} aria-hidden="true" />],
  ["showtimes", "Lịch chiếu", "showtimes.manage", <CalendarDays size={19} aria-hidden="true" />],
  ["prices", "Giá vé", "seat_types.manage", <Tags size={19} aria-hidden="true" />],
  ["employees", "Nhân viên", "users.manage", <Users size={19} aria-hidden="true" />],
  ["roles", "Phân quyền", "roles.manage", <Shield size={19} aria-hidden="true" />],
  ["documents", "Tài liệu chatbot", "knowledge.manage", <BookOpen size={19} aria-hidden="true" />],
  ["reports", "Báo cáo thống kê", "reports.view", <ChartColumn size={19} aria-hidden="true" />],
];

export default function AdminLayout() {
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    if (!getAccessToken()) {
      navigate("/login", { replace: true, state: { redirectTo: location.pathname } });
      return;
    }
    const controller = new AbortController();
    api.get("/admin/session", { signal: controller.signal }).then(({ data }) => {
      setSession(data);
      setError("");
    }).catch((err) => {
      if (err.code !== "ERR_CANCELED") setError(err.response?.status === 403
        ? "Tài khoản của bạn không có quyền truy cập khu vực này hoặc đã bị khóa."
        : "Không thể tải quyền truy cập. Vui lòng thử lại.");
    });
    return () => controller.abort();
  }, [attempt, location.pathname, navigate]);
  useEffect(() => {
    const sync = () => {
      setSession(null);
      setAttempt((n) => n + 1);
    };
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const allowed = sections.filter(([, , permission]) => session?.permissions.includes(permission));
  const firstPath = allowed[0]?.[0];
  const current = sections.find(([path]) => location.pathname.split("/")[2] === path);
  const permitted = !current || session?.permissions.includes(current[2]);
  useEffect(() => {
    if (session && !error && location.pathname.replace(/\/$/, "") === "/admin" && firstPath) {
      navigate(`/admin/${firstPath}`, { replace: true });
    }
  }, [session, error, location.pathname, navigate, firstPath]);
  return <div className="admin-app">
    <a className="admin-skip" href="#admin-content">Đến nội dung</a>
    <aside className="admin-sidebar">
      <Link to="/admin" className="admin-brand">CGV <span>QUẢN TRỊ RẠP</span></Link>
      <p className="admin-nav-label">Không gian làm việc</p>
      <nav aria-label="Quản trị">{allowed.map(([path, label, , icon]) =>
        <NavLink key={path} to={`/admin/${path}`}>{icon}{label}</NavLink>)}</nav>
      <Link to="/" className="admin-back"><ArrowLeft size={17} /> Về trang đặt vé</Link>
    </aside>
    <div className="admin-main">
      <header className="admin-topbar"><span>Hệ thống quản lý rạp chiếu phim</span>
        <div><span>{session?.user.full_name || session?.user.username}</span>
          {session && <span className="admin-badge">{{ ADMIN: "Quản trị viên", MANAGER: "Quản lý", STAFF: "Nhân viên" }[session.user.role] || session.user.role}</span>}
          <button title="Đăng xuất" aria-label="Đăng xuất" onClick={async () => {
            try { await api.post("/auth/logout"); }
            catch { /* Local sign-out remains available when the server cannot be reached. */ }
            finally { clearSession(); navigate("/login"); }
          }}><LogOut size={18} /></button>
        </div>
      </header>
      <main id="admin-content" className="admin-content">
        {error ? <div className="admin-panel"><h1>Không thể truy cập</h1><p role="alert">{error}</p>
          <button onClick={() => setAttempt((n) => n + 1)}>Thử lại</button> <Link to="/">Về trang chủ</Link></div>
          : !session ? <p role="status">Đang kiểm tra quyền truy cập…</p>
            : !permitted ? <div className="admin-panel"><h1>Không đủ quyền</h1><p>Bạn chưa được cấp quyền cho chức năng này.</p></div>
              : <Outlet context={{ ...session, refreshSession: () => setAttempt((n) => n + 1) }} />}
      </main>
    </div>
  </div>;
}
