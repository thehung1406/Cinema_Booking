import { useLocation } from "react-router-dom";
import { Button } from "./ui/Primitives";

export default function NotFound() {
  const admin = useLocation().pathname.startsWith("/admin");
  return <section className="shell page-section"><p className="error-code" aria-hidden="true">404</p><h1 className="page-title">Không tìm thấy trang</h1><p className="text-gray-600 mb-8">Đường dẫn này không còn tồn tại hoặc chưa chính xác.</p><div className="flex flex-wrap gap-3"><Button to={admin ? "/admin" : "/"}>{admin ? "Về khu quản trị" : "Về trang chủ"}</Button>{!admin && <Button to="/movie" variant="secondary">Xem danh sách phim</Button>}</div></section>;
}
