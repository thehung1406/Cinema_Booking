import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FaCalendarAlt, FaClock, FaFilm, FaLanguage, FaClosedCaptioning } from "react-icons/fa";
import api from "../config/api";

const Movie = () => {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // Thêm bộ lọc: all, showing, upcoming
  const navigate = useNavigate();
  const handleMovieDetail = (movieId) => {
    const movieId1 = movieId || "";
    navigate(`/MovieDetail/${movieId1}`);
  };
  // Fetch all movies on component mount
  useEffect(() => {
    const fetchMovies = async () => {
      try {
        setLoading(true);
        // Gọi API GET /films/ từ backend
        const response = await api.get("/films/");
        
        // Lấy chi tiết cho từng phim để có thêm thông tin language, subtitle, release_date
        const detailedMovies = await Promise.all(
          response.data.map(async (film) => {
            try {
              const detailRes = await api.get(`/films/${film.id}`);
              return detailRes.data;
            } catch (err) {
              console.error(`Lỗi khi lấy chi tiết phim ${film.id}:`, err);
              return film; // Fallback về dữ liệu cơ bản nếu lỗi
            }
          })
        );
        
        setMovies(detailedMovies);
        setLoading(false);
      } catch (error) {
        console.error('Lỗi khi lấy dữ liệu phim:', error);
        setLoading(false);
      }
    };
    fetchMovies();
  }, []);
  const handleBooking = (e) => {
    e.stopPropagation(); // Ngăn sự kiện click lan tỏa lên phần tử cha
    navigate(`/TicketBooking`);
  };
  
  // Kiểm tra phim đang chiếu dựa vào ngày hiện tại
  const isNowShowing = (movie) => {
    if (!movie.release_date) return false;
    const today = new Date();
    const releaseDate = new Date(movie.release_date);
    const endDate = movie.end_date ? new Date(movie.end_date) : new Date(releaseDate.getTime() + 90 * 24 * 60 * 60 * 1000); // Mặc định 90 ngày
    return today >= releaseDate && today <= endDate;
  };
  
  // Lọc phim theo trạng thái
  const filteredMovies = filter === "all" 
    ? movies 
    : movies.filter(movie => 
        filter === "showing" 
          ? isNowShowing(movie)
          : !isNowShowing(movie) // Sắp chiếu là chưa đến release_date
      );
  // Format ngày phát hành
  const formatReleaseDate = (dateString) => {
    const options = { day: '2-digit', month: '2-digit', year: 'numeric' };
    return new Date(dateString).toLocaleDateString('vi-VN', options);
  };
  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          <p className="mt-4 text-gray-600">Đang tải danh sách phim...</p>
        </div>
      </div>
    );
  }
  return (
    <div className="bg-gray-100 min-h-screen">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-center mb-8 text-gray-800">Danh sách phim</h1>
        {/* Bộ lọc phim */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex rounded-md shadow-sm" role="group">
            <button 
              className={`px-4 py-2 text-sm font-medium rounded-l-lg ${filter === "all" 
                ? "bg-red-600 text-white" 
                : "bg-white text-gray-700 hover:bg-gray-50"}`}
              onClick={() => setFilter("all")}
            >
              Tất cả
            </button>
            <button 
              className={`px-4 py-2 text-sm font-medium ${filter === "showing" 
                ? "bg-red-600 text-white" 
                : "bg-white text-gray-700 hover:bg-gray-50"}`}
              onClick={() => setFilter("showing")}
            >
              Đang chiếu
            </button>
            <button 
              className={`px-4 py-2 text-sm font-medium rounded-r-lg ${filter === "upcoming" 
                ? "bg-red-600 text-white" 
                : "bg-white text-gray-700 hover:bg-gray-50"}`}
              onClick={() => setFilter("upcoming")}
            >
              Sắp chiếu
            </button>
          </div>
        </div>
        
        {filteredMovies.length === 0 ? (
          <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 rounded-md">
            <p className="text-center">Không có phim nào trong danh mục này.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {filteredMovies.map((movie) => (
              <div 
                key={movie.id}
                className="bg-white rounded-lg shadow-md overflow-hidden transition-transform duration-300 hover:shadow-xl hover:-translate-y-2 cursor-pointer"
                onClick={() => handleMovieDetail(movie.id)}
              >
                <div className="relative">
                  <img 
                    src={movie.image || "/images/movie-placeholder.jpg"} 
                    alt={movie.title}
                    className="w-full h-64 object-cover"
                  />
                  <div className="absolute top-0 right-0 m-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-sm font-medium bg-red-100 text-red-800">
                      {movie.rating}
                    </span>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black to-transparent p-4">
                    <h2 className="text-white font-bold text-xl line-clamp-2">{movie.title}</h2>
                  </div>
                </div>
                
                <div className="p-4">
                  <div className="flex items-center text-gray-500 text-sm mb-2">
                    <FaClock className="mr-1" />
                    <span>{movie.duration}</span>
                    <span className="mx-2">|</span>
                    <FaFilm className="mr-1" />
                    <span className="truncate">{movie.genre}</span>
                  </div>
                  
                  <div className="text-gray-500 text-sm mb-2 flex items-center">
                    <FaLanguage className="mr-1" />
                    <span>{movie.language}</span>
                  </div>
                  
                  <div className="text-gray-500 text-sm mb-2 flex items-center">
                    <FaClosedCaptioning className="mr-1" />
                    <span>{movie.subtitle}</span>
                  </div>
                  
                  <div className="text-gray-500 text-sm mb-3 flex items-center">
                    <FaCalendarAlt className="mr-1" />
                    <span>{formatReleaseDate(movie.release_date)}</span>
                  </div>
                  
                  <div className="mt-4">
                    {isNowShowing(movie) ? (
                      <button 
                        onClick={(e) => handleBooking(e)}
                        className="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-md transition-colors duration-300"
                      >
                        Đặt vé
                      </button>
                    ) : (
                      <button 
                        onClick={(e) => handleBooking(e)}
                        className="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-md transition-colors duration-300"
                      >
                        Đặt vé trước
                      </button>
                    )}
                  </div>
                </div>
                
                <div className="px-4 pb-4">
                  <div className={`text-xs font-medium px-2 py-1 rounded-full text-center ${
                    isNowShowing(movie)
                      ? "bg-green-100 text-green-800" 
                      : "bg-yellow-100 text-yellow-800"
                  }`}>
                    {isNowShowing(movie) ? "Đang chiếu" : "Sắp chiếu"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Movie;
