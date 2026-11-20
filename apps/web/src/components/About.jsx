import EditorialMoment from "./ui/EditorialMoment";
import { ArrowUpRight } from "lucide-react";
import { Button } from "./ui/Primitives";
import { Link } from "react-router-dom";

export default function About() {
  return <>
    <section className="shell about-hero page-section" data-enter><div>
      <p className="eyebrow">CGV Cinema Booking</p><h1>Phim, rạp và buổi xem của bạn</h1>
      <p className="about-content">Tìm phim, chọn suất chiếu và đặt ghế. Thanh toán qua VNPay, theo dõi đơn và xem vé điện tử trong tài khoản của bạn.</p>
      <Button to="/movie" variant="secondary">Xem phim tại rạp <ArrowUpRight size={18} /></Button>
    </div></section>
    <section className="shell page-section"><div className="section-heading"><h2>Buổi xem phim của bạn</h2></div>
      <p className="about-content">Từ bộ phim đầu tiên bạn chọn đến chiếc ghế trong phòng chiếu, mọi thông tin đặt vé được tập hợp trong một đơn.</p>
      <div className="about-paths">
        <Link to="/movie"><span>01 / Phim & lịch chiếu</span><p className="text-base text-gray-600">Xem nội dung, trailer và đánh giá trước khi chọn phim.</p><ArrowUpRight aria-hidden="true" /></Link>
        <Link to="/cinema"><span>02 / Rạp chiếu</span><p className="text-base text-gray-600">Tìm rạp theo thành phố, chọn ngày và giờ xem phù hợp.</p><ArrowUpRight aria-hidden="true" /></Link>
        <Link to="/user-info"><span>03 / Đơn vé của bạn</span><p className="text-base text-gray-600">Kiểm tra trạng thái thanh toán và vé đã được phát hành.</p><ArrowUpRight aria-hidden="true" /></Link>
      </div>
    </section>
    <EditorialMoment />
  </>;
}
