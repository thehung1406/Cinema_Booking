import React from 'react';
import { FaPlay, FaUsers, FaFilm, FaMapMarkerAlt, FaAward } from 'react-icons/fa';
function About() {
  return (
    <div className="bg-gray-100 min-h-screen">
      {/* Hero Section */}
      <div className="relative h-48 md:h-64 bg-cover bg-center">
        <div className="absolute inset-0 bg-black bg-opacity-60 flex flex-col items-center justify-center text-center px-4">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">CGV CINEMAS VIỆT NAM</h2>
          <p className="text-xl text-white max-w-3xl">Trải nghiệm điện ảnh đỉnh cao với hệ thống rạp chiếu phim hiện đại hàng đầu Việt Nam</p>
        </div>
      </div>
      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        <div className="space-y-8">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-2xl font-bold mb-6 text-gray-800">Về CGV Cinemas Việt Nam</h3>
            <div className="flex flex-col md:flex-row gap-8">
              <div className="md:w-2/3">
                <p className="text-gray-600 mb-4 leading-relaxed">
                  CGV là một trong những chuỗi rạp chiếu phim lớn nhất tại Việt Nam, thuộc sở hữu của tập đoàn CJ Group (Hàn Quốc). Từ năm 2011, CGV chính thức có mặt tại thị trường Việt Nam và nhanh chóng trở thành đơn vị dẫn đầu trong ngành công nghiệp điện ảnh.
                </p>
                <p className="text-gray-600 mb-4 leading-relaxed">
                  Với hơn 80 cụm rạp hiện đại trên toàn quốc, CGV không ngừng mang đến cho khán giả Việt Nam những trải nghiệm điện ảnh đẳng cấp quốc tế thông qua hệ thống phòng chiếu tiêu chuẩn, công nghệ hiện đại và dịch vụ chuyên nghiệp.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  CGV không chỉ là nơi để thưởng thức các bộ phim bom tấn từ khắp nơi trên thế giới mà còn là điểm đến giải trí tuyệt vời cho mọi lứa tuổi với các dịch vụ đa dạng và không gian trải nghiệm độc đáo.
                </p>
              </div>
              <div className="md:w-1/3">
                <img 
                  src="https://statics.vincom.com.vn/http/vincom-ho/thuong_hieu/anh_logo/CGV-Cinemas.png/8e6196f9adbc621156a5519c267b3e93.webp" 
                  alt="CGV Cinema" 
                  className="w-full h-auto rounded-lg shadow-md"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-xl transition-shadow">
              <div className="h-16 w-16 bg-red-100 text-red-700 rounded-full flex items-center justify-center mx-auto mb-4">
                <FaUsers className="text-2xl" />
              </div>
              <h4 className="text-xl font-bold mb-2 text-gray-800">10+ Triệu</h4>
              <p className="text-gray-600">Khách hàng thân thiết</p>
            </div>
            
            <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-xl transition-shadow">
              <div className="h-16 w-16 bg-red-100 text-red-700 rounded-full flex items-center justify-center mx-auto mb-4">
                <FaFilm className="text-2xl" />
              </div>
              <h4 className="text-xl font-bold mb-2 text-gray-800">500+</h4>
              <p className="text-gray-600">Phim chiếu mỗi năm</p>
            </div>
            
            <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-xl transition-shadow">
              <div className="h-16 w-16 bg-red-100 text-red-700 rounded-full flex items-center justify-center mx-auto mb-4">
                <FaMapMarkerAlt className="text-2xl" />
              </div>
              <h4 className="text-xl font-bold mb-2 text-gray-800">83+</h4>
              <p className="text-gray-600">Cụm rạp trên toàn quốc</p>
            </div>
            
            <div className="bg-white rounded-lg shadow-md p-6 text-center hover:shadow-xl transition-shadow">
              <div className="h-16 w-16 bg-red-100 text-red-700 rounded-full flex items-center justify-center mx-auto mb-4">
                <FaAward className="text-2xl" />
              </div>
              <h4 className="text-xl font-bold mb-2 text-gray-800">15+</h4>
              <p className="text-gray-600">Năm kinh nghiệm</p>
            </div>
          </div>

          
        </div>

        {/* CTA Section */}
        <div className="bg-red-700 text-white rounded-lg shadow-md p-6 mt-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between">
            <div className="mb-6 md:mb-0 md:mr-8">
              <h3 className="text-2xl font-bold mb-2">Trở thành thành viên CGV</h3>
              <p className="text-white text-opacity-90">Đăng ký ngay để nhận nhiều ưu đãi hấp dẫn và trải nghiệm dịch vụ tốt nhất từ CGV</p>
            </div>
            <div>
              <a 
                href="#" 
                className="inline-block bg-white hover:bg-gray-100 text-red-700 font-bold py-3 px-6 rounded-lg transition-colors"
              >
                Đăng ký ngay
              </a>
            </div>
          </div>
        </div>
      </div>

      
    </div>
  );
}

export default About;
