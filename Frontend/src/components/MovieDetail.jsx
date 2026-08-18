import React, { useState, useEffect } from "react";
import { FaStar, FaCalendarAlt, FaClock, FaFilm, FaTicketAlt, FaPlay, FaMapMarkerAlt, FaLanguage, FaClosedCaptioning } from "react-icons/fa";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";

const API_BASE_URL = 'http://localhost:8000';

function MovieDetail() {
  const { id } = useParams();
  const [isTrailerOpen, setIsTrailerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("synopsis");
  const [loading, setLoading] = useState(true);
  const [movie, setMovie] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleBooking = (e) => {
    e.stopPropagation(); // Ngăn sự kiện click lan tỏa lên phần tử cha
    navigate(`/TicketBooking`);
  };
  const formatDate = (dateString) => {
    if (!dateString) return "Chưa xác định";
    const date = new Date(dateString);
    return date.toLocaleDateString("vi-VN", {
      day: "numeric",
      month: "long",
      year: "numeric"
    });
  };

  useEffect(() => {
    const fetchMovieDetails = async () => {
      try {
        setLoading(true);
        // Gọi API GET /films/{film_id} từ backend
        const response = await axios.get(`${API_BASE_URL}/films/${id}`);
        setMovie(response.data);
        setLoading(false);
      } catch (err) {
        setError("Không thể tải thông tin phim. Vui lòng thử lại sau.");
        setLoading(false);
        console.error(err);
      }
    };

    fetchMovieDetails();
    // Scroll to top when component mounts
    window.scrollTo(0, 0);
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 px-4">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full text-center">
          <div className="text-red-500 text-5xl mb-4">
            <FaFilm className="mx-auto" />
          </div>
          <h2 className="text-2xl font-bold text-gray-800 mb-4">Đã xảy ra lỗi</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => navigate("/")}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition duration-300"
          >
            Quay lại trang chủ
          </button>
        </div>
      </div>
    );
  }

  if (!movie) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 px-4">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full text-center">
          <div className="text-yellow-500 text-5xl mb-4">
            <FaFilm className="mx-auto" />
          </div>
          <h2 className="text-2xl font-bold text-gray-800 mb-4">Không tìm thấy phim</h2>
          <p className="text-gray-600 mb-6">
            Phim bạn đang tìm kiếm không tồn tại hoặc đã bị xóa.
          </p>
          <button
            onClick={() => navigate("/")}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition duration-300"
          >
            Quay lại trang chủ
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="bg-gray-50 min-h-screen pb-12">
      {/* Hero Section with Backdrop */}
      <div
        className="w-full h-80 bg-cover bg-center relative"
        style={{
          backgroundImage: `linear-gradient(to bottom, rgba(0,0,0,0.7), rgba(0,0,0,0.8)), url(${
            movie.image || "https://via.placeholder.com/1200x600?text=No+Image"
          })`,
          backgroundPosition: "center 20%",
        }}
      >
        <div className="container mx-auto px-4 h-full flex items-end">
          <div className="pb-8">
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-2">
              {movie.title}
            </h1>
            <div className="flex flex-wrap items-center text-white opacity-90 gap-4">
              {movie.rating && (
                <span className="bg-red-600 text-white text-sm font-bold px-2 py-1 rounded">
                  {movie.rating}
                </span>
              )}
              {movie.duration && (
                <div className="flex items-center">
                  <FaClock className="mr-1" />
                  <span>{movie.duration}</span>
                </div>
              )}
              {movie.genre && <span>{movie.genre}</span>}
            </div>
          </div>
        </div>
      </div>
      {/* Main Content */}
      <div className="container mx-auto px-4 -mt-16 relative z-10">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          <div className="md:flex">
            {/* Poster Column */}
            <div className="md:w-1/3 p-6">
              <img
                src={
                  movie.image ||
                  "https://via.placeholder.com/400x600?text=No+Image"
                }
                alt={movie.title}
                className="w-full h-64 object-cover "
                onError={(e) => {
                  e.target.src =
                    "https://via.placeholder.com/400x600?text=No+Image";
                }}
              />
              <div className="mt-6 space-y-3">
                <button
                  onClick={() => setIsTrailerOpen(true)}
                  className="w-full bg-red-600 hover:bg-red-700 text-white py-3 px-4 rounded-lg flex items-center justify-center transition duration-300"
                >
                  <FaPlay className="mr-2" /> Xem trailer
                </button>
                <button
                 onClick={(e) => handleBooking(e,movie.id)}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg flex items-center justify-center transition duration-300"
                >
                  <FaTicketAlt className="mr-2" /> Đặt vé ngay
                </button>
              </div>
            </div>
            {/* Details Column */}
            <div className="md:w-2/3 p-6">
              {/* Tabs */}
              <div className="border-b border-gray-200 mb-6">
                <div className="flex space-x-8">
                  <button
                    className={`py-3 px-1 font-medium ${
                      activeTab === "synopsis"
                        ? "border-b-2 border-blue-600 text-blue-600"
                        : "text-gray-500 hover:text-gray-700"
                    } transition duration-200`}
                    onClick={() => setActiveTab("synopsis")}
                  >
                    Nội dung
                  </button>
                  <button
                    className={`py-3 px-1 font-medium ${
                      activeTab === "details"
                        ? "border-b-2 border-blue-600 text-blue-600"
                        : "text-gray-500 hover:text-gray-700"
                    } transition duration-200`}
                    onClick={() => setActiveTab("details")}
                  >
                    Chi tiết
                  </button>
                </div>
              </div>
              {/* Tab Content */}
              <div className="min-h-[300px]">
                {activeTab === "synopsis" && (
                  <div className="prose max-w-none">
                    <p className="text-gray-700 leading-relaxed">
                      {movie.description || "Chưa có nội dung cho phim này."}
                    </p>
                  </div>
                )}
                {activeTab === "details" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <div>
                        <h3 className="text-gray-500 text-sm font-medium mb-1">
                          Thể loại
                        </h3>
                        <p className="text-gray-900 font-medium">
                          {movie.genre || "Chưa xác định"}
                        </p>
                      </div>
                      <div>
                        <h3 className="text-gray-500 text-sm font-medium mb-1">
                          Thời lượng
                        </h3>
                        <p className="text-gray-900 font-medium">
                          {movie.duration || "Chưa xác định"}
                        </p>
                      </div>
                      <div>
                        <h3 className="text-gray-500 text-sm font-medium mb-1">
                          Khởi chiếu
                        </h3>
                        <p className="text-gray-900 font-medium">
                          {formatDate(movie.release_date)}
                        </p>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <div>
                        <h3 className="text-gray-500 text-sm font-medium mb-1">
                          Ngôn ngữ
                        </h3>
                        <p className="text-gray-900 font-medium">
                          {movie.language || "Tiếng Anh"}
                        </p>
                      </div>
                      <div>
                        <h3 className="text-gray-500 text-sm font-medium mb-1">
                          Phụ đề
                        </h3>
                        <p className="text-gray-900 font-medium">
                          {movie.subtitle || "Tiếng Việt"}
                        </p>
                      </div>
                      <div>
                        <h3 className="text-gray-500 text-sm font-medium mb-1">
                          Định dạng
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {movie.formats && movie.formats.length > 0 ? (
                            movie.formats.map((format, index) => (
                              <span
                                key={index}
                                className="bg-gray-100 text-gray-800 text-xs font-medium px-2.5 py-1 rounded"
                              >
                                {format}
                              </span>
                            ))
                          ) : (
                            <span className="bg-gray-100 text-gray-800 text-xs font-medium px-2.5 py-1 rounded">
                              2D
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        {/* Additional Info */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="text-blue-600 text-xl mb-4">
              <FaMapMarkerAlt className="inline-block mr-2" />
              <span className="font-bold">Rạp chiếu</span>
            </div>
            <p className="text-gray-700">
              Phim đang được chiếu tại nhiều rạp trên toàn quốc. Nhấn "Đặt vé
              ngay" để xem danh sách rạp.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="text-blue-600 text-xl mb-4">
              <FaLanguage className="inline-block mr-2" />
              <span className="font-bold">Ngôn ngữ</span>
            </div>
            <p className="text-gray-700">
              Phim được chiếu bằng tiếng {movie.language || "Anh"} với phụ đề{" "}
              {movie.subtitle || "Việt"}.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="text-blue-600 text-xl mb-4">
              <FaClosedCaptioning className="inline-block mr-2" />
              <span className="font-bold">Định dạng</span>
            </div>
            <p className="text-gray-700">
              Phim được chiếu với các định dạng:{" "}
              {movie.formats && movie.formats.length > 0
                ? movie.formats.join(", ")
                : "2D"}
            </p>
          </div>
        </div>
      </div>
      {/* Trailer Modal */}
      {isTrailerOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg overflow-hidden w-full max-w-4xl">
            <div className="w-full aspect-video">
              <iframe
                className="w-full h-full"
                src={movie.trailer}
                title={`${movie.title} Trailer`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              ></iframe>
            </div>
            <div className="p-4 flex justify-end">
              <button
                onClick={() => setIsTrailerOpen(false)}
                className="bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded transition duration-300"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MovieDetail;
