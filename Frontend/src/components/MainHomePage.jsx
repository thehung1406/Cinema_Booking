import React from "react";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../config/api";

const MainHomePage = () => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [featuredMovies, setFeaturedMovies] = useState([]);
  const [nowShowingMovies, setNowShowingMovies] = useState([]);
  const [upcomingMovies, setUpcomingMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const handleMovieDetail = (movieId) => {
    const movieId1 = movieId || "";
    navigate(`/MovieDetail/${movieId1}`);
};
  const handleBooking = (e) => {
    e.stopPropagation(); // Ngăn sự kiện click lan tỏa lên phần tử cha
    navigate(`/TicketBooking`);
  };
  
  // Kiểm tra phim đang chiếu dựa vào ngày hiện tại
  const isNowShowing = (movie) => {
    if (!movie.release_date) return false;
    const today = new Date();
    const releaseDate = new Date(movie.release_date);
    const endDate = movie.end_date ? new Date(movie.end_date) : new Date(releaseDate.getTime() + 90 * 24 * 60 * 60 * 1000);
    return today >= releaseDate && today <= endDate;
  };
  
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Gọi API GET /films/ từ backend
        const response = await api.get("/films/");
        
        // Lấy chi tiết cho từng phim
        const detailedMovies = await Promise.all(
          response.data.map(async (film) => {
            try {
              const detailRes = await api.get(`/films/${film.id}`);
              return detailRes.data;
            } catch (err) {
              console.error(`Lỗi khi lấy chi tiết phim ${film.id}:`, err);
              return film;
            }
          })
        );
        
        // Phân loại phim
        const nowShowing = detailedMovies.filter(movie => isNowShowing(movie));
        const upcoming = detailedMovies.filter(movie => !isNowShowing(movie));
        
        // Featured movies là phim đang chiếu (lấy 5 phim đầu)
        setFeaturedMovies(nowShowing.slice(0, 5));
        setNowShowingMovies(nowShowing.slice(0, 8));
        setUpcomingMovies(upcoming.slice(0, 8));
        
        setLoading(false);
      } catch (error) {
        console.error("Lỗi khi lấy dữ liệu:", error);
        setLoading(false);
      }
    };
    fetchData();
  }, []);
  // Auto-rotate carousel
  useEffect(() => {
    if (featuredMovies.length === 0) return;
    const interval = setInterval(() => {
      setCurrentSlide((prevSlide) =>
        prevSlide === featuredMovies.length - 1 ? 0 : prevSlide + 1
      );
    }, 5000);
    return () => clearInterval(interval);
  }, [featuredMovies.length]);
  const goToSlide = (index) => {
    setCurrentSlide(index);
  };
  if (loading) {
    return <div>Đang tải dữ liệu...</div>;
  }
  return (
    <div>
      {/* Hero Carousel */}
      <div className="relative bg-black">
        <div className="h-96 md:h-128 overflow-hidden">
          {featuredMovies.map((movie, index) => (
            <div
              key={movie.id}
              className={`absolute w-full h-full transition-opacity duration-1000 ease-in-out ${
                index === currentSlide ? "opacity-100" : "opacity-0"
              }`}
            >
              <img
                src={movie.image}
                alt={movie.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent">
                <div className="absolute bottom-0 left-0 p-8">
                  <h2 className="text-white text-4xl font-bold mb-2">
                    {movie.title}
                  </h2>
                  <p className="text-gray-300 mb-4">{movie.genre}</p>
                  <button className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded-md text-white font-medium"
                  onClick={(e) => handleBooking(e, movie.id)}>
                    Đặt vé ngay
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Carousel indicators */}
        <div className="absolute bottom-4 left-0 right-0">
          <div className="flex justify-center space-x-2">
          {featuredMovies.map((movie, index) => (
              <button
                key={movie.id}
                onClick={() => goToSlide(index)}
                className={`h-2 rounded-full transition-all ${
                  currentSlide === index ? "w-8 bg-red-600" : "w-2 bg-gray-400"
                }`}
              ></button>
            ))}
          </div>
        </div>
      </div>
     
      {/* Now Showing */}
      <section className="py-12 m-20">
        <div className="container mx-auto px-4">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-2xl font-bold">Phim Đang Chiếu</h2>
            <a
              href="movie"
              className="text-red-600 hover:text-red-700 font-medium"
            >
              Xem tất cả
            </a>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {nowShowingMovies.map((movie) => (
              <div
                key={movie.id}
                className="bg-white rounded-lg shadow-md overflow-hidden ursor-pointer transform hover:scale-105 transition"
                onClick={() => handleMovieDetail(movie.id)}
              >
                <div className="relative">
                  <img
                    src={movie.image}
                    alt={movie.title}
                    className="w-full h-64 object-cover "
                  />
                  <div className="absolute top-2 right-2 bg-gray-900 text-white px-2 py-1 rounded">
                    {movie.rating}
                  </div>
                </div>
                <div className="p-4">
                  <h3 className="text-lg font-semibold mb-1">{movie.title}</h3>
                  <p className="text-gray-600 text-sm mb-3">{movie.genre}</p>
                  <button
                    className="w-full bg-red-600 hover:bg-red-700 text-white py-2 rounded font-medium"
                    onClick={(e) => handleBooking(e, movie.id)}
                  >
                    Đặt vé
                  </button>
                </div>
              </div>
            ))}
          </div>  
        </div>
      </section>
      {/* Upcoming Movies */}
      <section className="py-12 m-20">
        <div className="container mx-auto px-4">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-2xl font-bold">Phim Sắp Chiếu</h2>
            <a
              href="movie"
              className="text-red-600 hover:text-red-700 font-medium"
            >
              Xem tất cả
            </a>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {upcomingMovies.map((movie) => (
              <div
                key={movie.id}
                className="bg-white rounded-lg shadow-md overflow-hidden ursor-pointer transform hover:scale-105 transition"
                onClick={() => handleMovieDetail(movie.id)}
              >
                <div className="relative">
                  <img
                    src={movie.image}
                    alt={movie.title}
                    className="w-full h-64 object-cover "
                  />
                  <div className="absolute top-2 right-2 bg-gray-900 text-white px-2 py-1 rounded">
                    {movie.rating}
                  </div>
                </div>
                <div className="p-4">
                  <h3 className="text-lg font-semibold mb-1">{movie.title}</h3>
                  <p className="text-gray-600 text-sm mb-3">{movie.genre}</p>
                  <button
                    className="w-full bg-red-600 hover:bg-red-700 text-white py-2 rounded font-medium "
                    onClick={handleBooking}
                  >
                    Đặt vé trước
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="bg-gray-900 text-white py-16">
        <div className="container mx-auto px-4">
          <h2 className="text-2xl font-bold mb-12 text-center">
            Tại sao chọn CGV?
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="bg-red-600 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <svg
                  className="h-8 w-8 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z"
                  />
                </svg>
              </div>
              <h3 className="text-xl font-semibold mb-2">Đặt vé dễ dàng</h3>
              <p className="text-gray-400">
                Đặt vé chỉ với vài thao tác đơn giản, thanh toán nhanh chóng và
                an toàn.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-red-600 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <svg
                  className="h-8 w-8 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <h3 className="text-xl font-semibold mb-2">Giá cả ưu đãi</h3>
              <p className="text-gray-400">
                Chương trình khuyến mãi thường xuyên và giá vé ưu đãi cho thành
                viên.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-red-600 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <svg
                  className="h-8 w-8 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
              </div>
              <h3 className="text-xl font-semibold mb-2">
                Trải nghiệm cao cấp
              </h3>
              <p className="text-gray-400">
                Hệ thống rạp chiếu hiện đại với âm thanh và hình ảnh chất lượng
                cao.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Newsletter */}
      <section className="bg-red-600 py-12">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-2xl font-bold text-white mb-4">
            Đăng ký nhận thông tin khuyến mãi
          </h2>
          <p className="text-white opacity-90 mb-6 max-w-2xl mx-auto">
            Nhận thông báo về phim mới, sự kiện đặc biệt và ưu đãi độc quyền qua
            email.
          </p>

          <div className="max-w-md mx-auto flex">
            <input
              type="email"
              placeholder="Nhập email của bạn"
              className="flex-1 px-4 py-3 rounded-l-md focus:outline-none text-white bg-gray-900"
            />
            <button className="bg-gray-900 text-white px-6 py-3 rounded-r-md hover:bg-gray-800 transition-colors">
              Đăng ký
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default MainHomePage;
