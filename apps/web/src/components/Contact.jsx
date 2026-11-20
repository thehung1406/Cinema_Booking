import { ArrowUpRight, Mail } from "lucide-react";
import { Link } from "react-router-dom";

const groups = [
  ["Đặt vé", [
    ["Đặt vé xem phim như thế nào?", "Chọn phim, rạp, ngày và suất chiếu. Chọn ghế, thêm bắp nước nếu cần, kiểm tra đơn rồi thanh toán qua VNPay."],
    ["Ghế được giữ trong bao lâu?", "Thời điểm hết hạn giữ ghế được hiển thị trong luồng đặt vé. Khi hết hạn, hãy quay lại sơ đồ và chọn ghế còn trống."],
    ["Có bắt buộc mua bắp nước không?", "Không. Ở bước bắp nước, chọn “Bỏ qua, chỉ mua vé” để tiếp tục."]
  ]],
  ["Thanh toán & vé điện tử", [
    ["Đã thu tiền nhưng chưa thấy vé?", "Kiểm tra lại trạng thái trong đơn vé. Nếu hệ thống đang xác nhận hoặc cần đối soát, không thanh toán lại. Gửi mã đơn cho bộ phận hỗ trợ để kiểm tra."],
    ["Xem mã vé ở đâu?", "Trong tài khoản, mở đơn đã được xác nhận và chọn xem kết quả, vé điện tử. Mã QR xuất hiện khi hệ thống đã phát hành và tải được vé."],
    ["Tôi muốn đổi hoặc hủy vé đã mua?", "Liên hệ hỗ trợ và cung cấp mã đơn để được kiểm tra trường hợp cụ thể. Website hiện chưa có thao tác tự đổi hoặc hủy vé."]
  ]],
  ["Tài khoản", [
    ["Tôi cần tài khoản để đặt vé không?", "Bạn cần đăng nhập để giữ ghế và tạo đơn. Sau khi đăng nhập, bạn có thể tiếp tục luồng đặt vé."],
    ["Cập nhật thông tin cá nhân ở đâu?", "Mở tài khoản, chọn chỉnh sửa thông tin và lưu thay đổi. Lịch sử đơn vé nằm trong cùng trang."]
  ]]
];
export default function Contact() {
  return <div className="shell page-section"><p className="eyebrow">Hỗ trợ khách hàng</p><h1 className="page-title">Thông tin cho buổi xem phim</h1><p className="text-gray-600 mb-12">Hướng dẫn đặt vé, kiểm tra thanh toán và quản lý tài khoản.</p>
    <div className="support-grid"><div>{groups.map(([title, faqs]) => <section key={title} className="faq-group"><h2>{title}</h2>{faqs.map(([question, answer]) => <article className="faq-item" key={question}><h3>{question}</h3><p>{answer}</p></article>)}</section>)}</div>
      <aside className="surface booking-summary"><Mail size={24} className="text-red-700 mb-6" aria-hidden="true" /><h2 className="text-xl mb-4">Liên hệ hỗ trợ</h2><p className="text-gray-600 leading-7 mb-6">Cung cấp mã đơn và mô tả vấn đề để bộ phận hỗ trợ kiểm tra.</p><a className="btn btn-primary w-full" href="mailto:hoidap@cgv.vn">Mở email hỗ trợ <ArrowUpRight size={18} /></a><p className="text-sm text-gray-600 mt-4">Ứng dụng email của bạn sẽ mở để soạn thư.</p><Link className="btn btn-ghost w-full mt-4" to="/user-info">Xem đơn vé</Link></aside>
    </div>
  </div>;
}
