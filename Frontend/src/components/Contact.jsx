import React, { useState } from 'react';
import { FaMapMarkerAlt, FaPhone, FaEnvelope, FaClock, FaFacebookF, FaTwitter, FaInstagram, FaYoutube, FaChevronRight } from 'react-icons/fa';

function Contact() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    subject: '',
    message: '',
    agreeTerms: false
  });
  
  const [formErrors, setFormErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState('contact');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    // Clear error when user types
    if (formErrors[name]) {
      setFormErrors(prev => ({
        ...prev,
        [name]: undefined
      }));
    }
  };

  const validateForm = () => {
    const errors = {};
    
    if (!formData.name.trim()) {
      errors.name = 'Vui lòng nhập họ tên';
    }
    
    if (!formData.email.trim()) {
      errors.email = 'Vui lòng nhập email';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'Email không hợp lệ';
    }
    
    if (!formData.phone.trim()) {
      errors.phone = 'Vui lòng nhập số điện thoại';
    } else if (!/^[0-9]{10,11}$/.test(formData.phone.replace(/\s/g, ''))) {
      errors.phone = 'Số điện thoại không hợp lệ';
    }
    
    if (!formData.subject.trim()) {
      errors.subject = 'Vui lòng chọn chủ đề';
    }
    
    if (!formData.message.trim()) {
      errors.message = 'Vui lòng nhập nội dung';
    } else if (formData.message.length < 20) {
      errors.message = 'Nội dung quá ngắn (tối thiểu 20 ký tự)';
    }
    
    if (!formData.agreeTerms) {
      errors.agreeTerms = 'Vui lòng đồng ý với điều khoản';
    }
    
    return errors;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }
    
    setIsSubmitting(true);
    
    // Simulate API call
    setTimeout(() => {
      setIsSubmitting(false);
      setSubmitSuccess(true);
      
      // Reset form after 3 seconds
      setTimeout(() => {
        setSubmitSuccess(false);
        setFormData({
          name: '',
          email: '',
          phone: '',
          subject: '',
          message: '',
          agreeTerms: false
        });
      }, 3000);
    }, 1500);
  };

  return (
    <div className="bg-gray-100 min-h-screen">   
     {/* Banner */}
      <div className="relative h-48 md:h-64 bg-cover bg-center" style={{backgroundImage: 'url(https://www.cgv.vn/media/wysiwyg/2023/022023/banner-contact-us.jpg)'}}>
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white text-center px-4">LIÊN HỆ VỚI CGV</h2>
        </div>
      </div>
      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex mb-6 border-b border-gray-300">
          <button 
            className={`py-3 px-5 font-medium text-lg ${activeTab === 'contact' ? 'text-red-700 border-b-2 border-red-700' : 'text-gray-600 hover:text-red-700'}`}
            onClick={() => setActiveTab('contact')}
          >
            Liên hệ
          </button>
          <button 
            className={`py-3 px-5 font-medium text-lg ${activeTab === 'faq' ? 'text-red-700 border-b-2 border-red-700' : 'text-gray-600 hover:text-red-700'}`}
            onClick={() => setActiveTab('faq')}
          >
            Câu hỏi thường gặp
          </button>
        </div>

        {activeTab === 'contact' ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Contact Info */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg shadow-md p-6 mb-6">
                <h3 className="text-xl font-bold mb-4 text-gray-800">Thông tin liên hệ</h3>
                
                <div className="space-y-4">
                  <div className="flex">
                    <div className="flex-shrink-0 h-10 w-10 rounded-full bg-red-100 flex items-center justify-center text-red-700">
                      <FaMapMarkerAlt />
                    </div>
                    <div className="ml-4">
                      <h4 className="text-base font-medium text-gray-800">Địa chỉ</h4>
                      <p className="text-gray-600">Tầng 2, Rivera Park Saigon - Số 7/28 Thành Thái, P.14, Q.10, TPHCM</p>
                    </div>
                  </div>
                  
                  <div className="flex">
                    <div className="flex-shrink-0 h-10 w-10 rounded-full bg-red-100 flex items-center justify-center text-red-700">
                      <FaPhone />
                    </div>
                    <div className="ml-4">
                      <h4 className="text-base font-medium text-gray-800">Hotline</h4>
                      <p className="text-gray-600">1900 6017</p>
                    </div>
                  </div>
                  
                  <div className="flex">
                    <div className="flex-shrink-0 h-10 w-10 rounded-full bg-red-100 flex items-center justify-center text-red-700">
                      <FaEnvelope />
                    </div>
                    <div className="ml-4">
                      <h4 className="text-base font-medium text-gray-800">Email</h4>
                      <p className="text-gray-600">hoidap@cgv.vn</p>
                    </div>
                  </div>
                  
                  <div className="flex">
                    <div className="flex-shrink-0 h-10 w-10 rounded-full bg-red-100 flex items-center justify-center text-red-700">
                      <FaClock />
                    </div>
                    <div className="ml-4">
                      <h4 className="text-base font-medium text-gray-800">Giờ làm việc</h4>
                      <p className="text-gray-600">Thứ 2 - Thứ 6: 8:00 - 17:30</p>
                      <p className="text-gray-600">Thứ 7: 8:00 - 12:00</p>
                    </div>
                  </div>
                </div>
                
                <div className="mt-6">
                  <h4 className="text-base font-medium text-gray-800 mb-3">Kết nối với chúng tôi</h4>
                  <div className="flex space-x-3">
                    <a href="#" className="h-10 w-10 rounded-full bg-blue-600 flex items-center justify-center text-white hover:bg-blue-700 transition-colors">
                      <FaFacebookF />
                    </a>
                    <a href="#" className="h-10 w-10 rounded-full bg-blue-400 flex items-center justify-center text-white hover:bg-blue-500 transition-colors">
                      <FaTwitter />
                    </a>
                    <a href="#" className="h-10 w-10 rounded-full bg-pink-600 flex items-center justify-center text-white hover:bg-pink-700 transition-colors">
                      <FaInstagram />
                    </a>
                    <a href="#" className="h-10 w-10 rounded-full bg-red-600 flex items-center justify-center text-white hover:bg-red-700 transition-colors">
                      <FaYoutube />
                    </a>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-xl font-bold mb-4 text-gray-800">Giờ mở cửa rạp chiếu</h3>
                <p className="text-gray-600 mb-3">Các rạp CGV mở cửa tất cả các ngày trong tuần, bao gồm cả các ngày lễ.</p>
                <ul className="space-y-2 text-gray-600">
                  <li className="flex justify-between">
                    <span>Thứ 2 - Thứ 6:</span>
                    <span className="font-medium">9:00 - 23:00</span>
                  </li>
                  <li className="flex justify-between">
                    <span>Thứ 7:</span>
                    <span className="font-medium">8:00 - 23:30</span>
                  </li>
                  <li className="flex justify-between">
                    <span>Chủ nhật:</span>
                    <span className="font-medium">8:00 - 23:00</span>
                  </li>
                  <li className="flex justify-between">
                    <span>Ngày lễ:</span>
                    <span className="font-medium">8:00 - 23:30</span>
                  </li>
                </ul>
                <p className="text-sm text-gray-500 mt-3">* Lịch mở cửa có thể thay đổi tùy theo từng rạp và ngày lễ cụ thể</p>
              </div>
            </div>
            
            {/* Contact Form */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-xl font-bold mb-4 text-gray-800">Gửi thông tin liên hệ</h3>
                <p className="text-gray-600 mb-6">Vui lòng điền đầy đủ thông tin bên dưới, chúng tôi sẽ liên hệ lại với bạn trong thời gian sớm nhất.</p>
                
                {submitSuccess ? (
                  <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-6">
                    <div className="flex items-center">
                      <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                      </svg>
                      <span className="font-medium">Gửi thông tin thành công!</span>
                    </div>
                    <p className="mt-2">Cảm ơn bạn đã liên hệ với CGV. Chúng tôi sẽ phản hồi trong thời gian sớm nhất.</p>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit}>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                      <div>
                        <label htmlFor="name" className="block text-gray-700 font-medium mb-2">Họ tên <span className="text-red-600">*</span></label>
                        <input 
                          type="text" 
                          id="name" 
                          name="name" 
                          value={formData.name}
                          onChange={handleChange}
                          className={`w-full p-3 border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 ${formErrors.name ? 'border-red-500' : 'border-gray-300'}`}
                          placeholder="Nhập họ tên của bạn"
                        />
                        {formErrors.name && <p className="text-red-500 text-sm mt-1">{formErrors.name}</p>}
                      </div>
                      
                      <div>
                        <label htmlFor="email" className="block text-gray-700 font-medium mb-2">Email <span className="text-red-600">*</span></label>
                        <input 
                          type="email" 
                          id="email" 
                          name="email" 
                          value={formData.email}
                          onChange={handleChange}
                          className={`w-full p-3 border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 ${formErrors.email ? 'border-red-500' : 'border-gray-300'}`}
                          placeholder="Nhập email của bạn"
                        />
                        {formErrors.email && <p className="text-red-500 text-sm mt-1">{formErrors.email}</p>}
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                      <div>
                        <label htmlFor="phone" className="block text-gray-700 font-medium mb-2">Số điện thoại <span className="text-red-600">*</span></label>
                        <input 
                          type="tel" 
                          id="phone" 
                          name="phone" 
                          value={formData.phone}
                          onChange={handleChange}
                          className={`w-full p-3 border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 ${formErrors.phone ? 'border-red-500' : 'border-gray-300'}`}
                          placeholder="Nhập số điện thoại của bạn"
                        />
                        {formErrors.phone && <p className="text-red-500 text-sm mt-1">{formErrors.phone}</p>}
                      </div>
                      
                      <div>
                        <label htmlFor="subject" className="block text-gray-700 font-medium mb-2">Chủ đề <span className="text-red-600">*</span></label>
                        <select 
                          id="subject" 
                          name="subject" 
                          value={formData.subject}
                          onChange={handleChange}
                          className={`w-full p-3 border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 ${formErrors.subject ? 'border-red-500' : 'border-gray-300'}`}
                        >
                          <option value="">-- Chọn chủ đề --</option>
                          <option value="general">Thông tin chung</option>
                          <option value="ticket">Vé xem phim</option>
                          <option value="membership">Thẻ thành viên</option>
                          <option value="promotion">Khuyến mãi</option>
                          <option value="technical">Vấn đề kỹ thuật</option>
                          <option value="feedback">Góp ý, phản hồi</option>
                          <option value="other">Khác</option>
                        </select>
                        {formErrors.subject && <p className="text-red-500 text-sm mt-1">{formErrors.subject}</p>}
                      </div>
                    </div>
                    
                    <div className="mb-4">
                      <label htmlFor="message" className="block text-gray-700 font-medium mb-2">Nội dung <span className="text-red-600">*</span></label>
                      <textarea 
                        id="message" 
                        name="message" 
                        value={formData.message}
                        onChange={handleChange}
                        rows="5" 
                        className={`w-full p-3 border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 ${formErrors.message ? 'border-red-500' : 'border-gray-300'}`}
                        placeholder="Nhập nội dung liên hệ của bạn"
                      ></textarea>
                      {formErrors.message && <p className="text-red-500 text-sm mt-1">{formErrors.message}</p>}
                    </div>
                    
                    <div className="mb-6">
                      <div className="flex items-start">
                        <div className="flex items-center h-5">
                          <input 
                            id="agreeTerms" 
                            name="agreeTerms" 
                            type="checkbox" 
                            checked={formData.agreeTerms}
                            onChange={handleChange}
                            className="w-4 h-4 border border-gray-300 rounded bg-gray-50 focus:ring-3 focus:ring-red-300"
                          />
                        </div>
                        <label htmlFor="agreeTerms" className="ml-2 text-sm font-medium text-gray-700">
                          Tôi đồng ý với <a href="#" className="text-red-700 hover:underline">chính sách bảo mật</a> và <a href="#" className="text-red-700 hover:underline">điều khoản sử dụng</a> của CGV
                        </label>
                      </div>
                      {formErrors.agreeTerms && <p className="text-red-500 text-sm mt-1">{formErrors.agreeTerms}</p>}
                    </div>
                    
                    <button 
                      type="submit" 
                      className="w-full bg-red-700 hover:bg-red-800 text-white font-bold py-3 px-4 rounded-lg transition-colors flex items-center justify-center"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <>
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Đang gửi...
                        </>
                      ) : 'Gửi thông tin'}
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-xl font-bold mb-6 text-gray-800">Câu hỏi thường gặp</h3>
            
            <div className="space-y-4">
              {faqData.map((faq, index) => (
                <FaqItem key={index} question={faq.question} answer={faq.answer} />
              ))}
            </div>
          </div>
        )}
      </div>
      {/* Map Section */}
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h3 className="text-xl font-bold mb-4 text-gray-800">Vị trí của chúng tôi</h3>
          <div className="h-96 w-full rounded-lg overflow-hidden">
            <iframe 
              src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3919.4241674197956!2d106.66472195081287!3d10.777599992283382!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x31752f3ae5e3a41f%3A0xce3951e0d8a3a90!2sRivera%20Park%20Saigon!5e0!3m2!1sen!2s!4v1651234567890!5m2!1sen!2s" 
              width="100%" 
              height="100%" 
              style={{border: 0}} 
              allowFullScreen="" 
              loading="lazy" 
              referrerPolicy="no-referrer-when-downgrade">
            </iframe>
          </div>
        </div>
      </div>
      
    </div>
  );
}
// Component hiển thị câu hỏi thường gặp
function FaqItem({ question, answer }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button 
        className="flex justify-between items-center w-full p-4 text-left bg-gray-50 hover:bg-gray-100 focus:outline-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="font-medium text-gray-800">{question}</span>
        <svg 
          className={`w-5 h-5 transition-transform ${isOpen ? 'transform rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24" 
          xmlns="http://www.w3.org/2000/svg"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
        </svg>
      </button>
      
      {isOpen && (
        <div className="p-4 border-t border-gray-200">
          <p className="text-gray-600">{answer}</p>
        </div>
      )}
    </div>
  );
}
// Dữ liệu câu hỏi thường gặp
const faqData = [
  {
    question: "Làm thế nào để đặt vé xem phim online?",
    answer: "Bạn có thể đặt vé xem phim online thông qua website chính thức của CGV hoặc ứng dụng CGV Cinemas trên điện thoại. Chọn phim, rạp, suất chiếu và ghế ngồi, sau đó thanh toán qua các hình thức như thẻ tín dụng, ví điện tử hoặc chuyển khoản ngân hàng."
  },
  {
    question: "Làm thế nào để trở thành thành viên CGV?",
    answer: "Để trở thành thành viên CGV, bạn có thể đăng ký tài khoản trên website hoặc ứng dụng CGV Cinemas. Sau khi đăng ký, bạn sẽ nhận được thẻ thành viên điện tử và bắt đầu tích lũy điểm với mỗi giao dịch tại CGV."
  },
  {
    question: "Tôi có thể hủy hoặc đổi vé đã mua không?",
    answer: "CGV không hỗ trợ đổi hoặc hoàn tiền vé đã mua. Tuy nhiên, trong một số trường hợp đặc biệt như suất chiếu bị hủy, bạn sẽ được hoàn tiền hoặc đổi sang suất chiếu khác. Vui lòng liên hệ trực tiếp với rạp hoặc hotline 1900 6017 để được hỗ trợ."
  },
  {
    question: "Tôi quên mật khẩu tài khoản CGV, phải làm sao?",
    answer: "Bạn có thể sử dụng chức năng 'Quên mật khẩu' trên trang đăng nhập của website hoặc ứng dụng CGV. Hệ thống sẽ gửi email hướng dẫn đặt lại mật khẩu đến địa chỉ email đã đăng ký. Nếu vẫn gặp vấn đề, vui lòng liên hệ hotline 1900 6017 để được hỗ trợ."
  },
  {
    question: "CGV có chấp nhận thanh toán bằng thẻ quà tặng không?",
    answer: "Có, CGV chấp nhận thanh toán bằng thẻ quà tặng (CGV Gift Card) cho các giao dịch mua vé xem phim và đồ ăn, thức uống tại quầy. Bạn cũng có thể sử dụng thẻ quà tặng để thanh toán khi đặt vé online trên website hoặc ứng dụng CGV Cinemas."
  },
  {
    question: "Làm thế nào để sử dụng điểm tích lũy CGV?",
    answer: "Điểm tích lũy CGV có thể được sử dụng để đổi lấy vé xem phim, đồ ăn, thức uống hoặc các phần quà đặc biệt. Để sử dụng điểm, bạn cần đăng nhập vào tài khoản thành viên và chọn hình thức thanh toán bằng điểm khi mua vé hoặc đồ ăn. Bạn cũng có thể đổi điểm tại quầy dịch vụ khách hàng tại các rạp CGV."
  },
  {
    question: "CGV có chính sách ưu đãi cho học sinh, sinh viên không?",
    answer: "Có, CGV có chương trình U22 dành cho khách hàng dưới 22 tuổi với giá vé ưu đãi chỉ 50.000đ vào thứ 2 hàng tuần. Ngoài ra, CGV còn có nhiều chương trình khuyến mãi khác dành cho học sinh, sinh viên trong các dịp đặc biệt. Vui lòng theo dõi website và fanpage của CGV để cập nhật thông tin mới nhất."
  },
  {
    question: "Tôi có thể mang đồ ăn, thức uống từ bên ngoài vào rạp không?",
    answer: "Theo quy định của CGV, khách hàng không được mang đồ ăn, thức uống từ bên ngoài vào rạp chiếu phim. CGV có quầy bán đồ ăn, thức uống đa dạng để phục vụ nhu cầu của khách hàng trong suốt thời gian xem phim."
  },
  {
    question: "Làm thế nào để tổ chức sinh nhật hoặc sự kiện riêng tại CGV?",
    answer: "CGV cung cấp dịch vụ tổ chức sinh nhật và sự kiện riêng tại rạp. Bạn có thể liên hệ trực tiếp với rạp CGV gần nhất hoặc gửi email đến địa chỉ hoidap@cgv.vn để được tư vấn và báo giá. CGV sẽ cung cấp các gói dịch vụ phù hợp với nhu cầu và ngân sách của bạn."
  },
  {
    question: "Tôi có thể xem lịch chiếu phim sắp ra mắt ở đâu?",
    answer: "Bạn có thể xem lịch chiếu phim sắp ra mắt trên website chính thức của CGV (www.cgv.vn), ứng dụng CGV Cinemas hoặc theo dõi fanpage Facebook của CGV. Thông tin về các phim sắp chiếu thường được cập nhật trước 1-2 tuần."
  }
];
export default Contact;