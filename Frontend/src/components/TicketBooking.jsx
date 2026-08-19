import { useEffect, useState } from "react";
import {
  FaArrowRight,
  FaCalendarAlt,
  FaFilm,
  FaMapMarkerAlt,
  FaTicketAlt,
} from "react-icons/fa";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../config/api";

function TicketBooking() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialFilmId = searchParams.get("filmId") || searchParams.get("movieId") || "";
  const initialTheaterId = searchParams.get("theaterId") || searchParams.get("cinemaId") || "";

  const [movies, setMovies] = useState([]);
  const [selectedMovie, setSelectedMovie] = useState(initialFilmId);
  const [cinemas, setCinemas] = useState([]);
  const [selectedCinema, setSelectedCinema] = useState(initialTheaterId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [showtimes, setShowtimes] = useState([]);
  const [selectedShowtime, setSelectedShowtime] = useState(null);
  
  const fetchShowtimes = async (filmId, theaterId, date) => {
    try {
      setLoading(true);
      setError(null);
      // Gọi API GET /showtimes với query parameters
      const response = await api.get("/showtimes", {
        params: {
          film_id: parseInt(filmId),
          theater_id: parseInt(theaterId),
          date: date
        }
      });
      console.log("Dữ liệu suất chiếu từ API:", response.data);
      setShowtimes(response.data);
      setLoading(false);
    } catch (error) {
      console.error("Lỗi khi lấy suất chiếu:", error);
      setShowtimes([]);
      setLoading(false);
    }
  const loadTheatersForFilm = async (movieId) => {
    if (!movieId) {
      setCinemas([]);
      setSelectedCinema("");
      return [];
    }

    try {
      setLoading(true);
      setError(null);
      console.log('Đang tải danh sách rạp có chiếu phim...');

      // Gọi API GET /theater/by-film/{film_id} để lấy danh sách rạp chiếu phim này
      const response = await api.get(`/theater/by-film/${movieId}`);

      console.log('Response từ API:', response.data);

      let theaterList = [];
      if (Array.isArray(response.data)) {
        theaterList = response.data;
      } else if (response.data && typeof response.data === 'object') {
        theaterList = response.data.theaters || response.data.data || [response.data];
      }

      console.log('Danh sách rạp đã xử lý:', theaterList);
      setCinemas(theaterList);
      setLoading(false);
      return theaterList;
    } catch (error) {
      console.error("Lỗi khi lấy danh sách rạp:", error);
      console.error("Chi tiết lỗi:", error.response?.data);
      setError("Không thể tải danh sách rạp. Vui lòng thử lại sau.");
      setCinemas([]);
      setLoading(false);
      return [];
    }
  };

  // Fetch movies on component mount and handle pre-selected movie/theater
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Gọi API GET /films/ từ backend
        const moviesResponse = await api.get("/films/");
        setMovies(moviesResponse.data);

        if (initialFilmId) {
          setSelectedMovie(initialFilmId);
          const theaterList = await loadTheatersForFilm(initialFilmId);
          if (initialTheaterId && theaterList.some(t => String(t.id) === String(initialTheaterId))) {
            setSelectedCinema(initialTheaterId);
            fetchShowtimes(initialFilmId, initialTheaterId, selectedDate);
          }
        }
        setLoading(false);
      } catch (err) {
        console.error("Lỗi khi lấy dữ liệu:", err);
        setError("Không thể tải dữ liệu. Vui lòng thử lại sau.");
        setLoading(false);
      }
    };
    fetchData();
  }, [initialFilmId, initialTheaterId, selectedDate]);

  // Handle movie selection
  const handleSelectMovie = async (e) => {
    const movieId = e.target.value;
    setSelectedMovie(movieId);
    setSelectedShowtime(null);
    setShowtimes([]);
    setSelectedCinema("");

    if (!movieId) {
      setCinemas([]);
      return;
    }

    await loadTheatersForFilm(movieId);
  };

  // Handle cinema selection
  const handleSelectCinema = (e) => {
    const cinemaId = e.target.value;
    setSelectedCinema(cinemaId);
    setShowtimes([]);
    setSelectedShowtime(null);

    if (cinemaId && selectedMovie && selectedDate) {
      fetchShowtimes(selectedMovie, cinemaId, selectedDate);
    }
  };

  // Handle date selection
  const handleDateChange = (e) => {
    const newDate = e.target.value;
    setSelectedDate(newDate);

    if (selectedMovie && selectedCinema && newDate) {
      fetchShowtimes(selectedMovie, selectedCinema, newDate);
    }
  };

  // Navigate to seat booking page
  const handleNext = () => {
    if (!selectedMovie) {
      alert("Vui lòng chọn phim");
      return;
    }
    if (!selectedCinema) {
      alert("Vui lòng chọn rạp");
      return;
    }
    if (!selectedDate) {
      alert("Vui lòng chọn ngày");
      return;
    }
    if (!selectedShowtime) {
      alert("Vui lòng chọn suất chiếu");
      return;
    }
    navigate(`/seat-selection/${selectedShowtime}`);
  };
  // Loading state
  if (loading && movies.length === 0) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }
  // Error state
  if (error && movies.length === 0) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div
          className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative"
          role="alert"
        >
          <strong className="font-bold">Lỗi! </strong>
          <span className="block sm:inline">{error}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-center mb-8">Đặt vé xem phim</h1>

      <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Movie selection */}
          <div className="space-y-2">
            <label className="block text-gray-700 font-medium mb-2">
              <FaFilm className="inline mr-2" />
              Chọn phim
            </label>
            <select
              className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={selectedMovie}
              onChange={handleSelectMovie}
            >
              <option value="">-- Chọn phim --</option>
              {movies.map((movie) => (
                <option key={movie.id} value={movie.id}>
                  {movie.title}
                </option>
              ))}
            </select>
          </div>

          {/* Cinema selection */}
          <div className={`space-y-2 ${!selectedMovie ? "opacity-50" : ""}`}>
            <label className="block text-gray-700 font-medium mb-2">
              <FaMapMarkerAlt className="inline mr-2" />
              Chọn rạp
            </label>
            <select
              className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={selectedCinema}
              onChange={handleSelectCinema}
              disabled={!selectedMovie}
            >
              <option value="">-- Chọn rạp --</option>
              {cinemas.map((cinema) => (
                <option key={cinema.id || cinema.theater_id} value={cinema.id || cinema.theater_id}>
                  {cinema.name || cinema.theater_name}
                </option>
              ))}
            </select>
          </div>

          {/* Date selection */}
          <div className={`space-y-2 ${!selectedCinema ? "opacity-50" : ""}`}>
            <label className="block text-gray-700 font-medium mb-2">
              <FaCalendarAlt className="inline mr-2" />
              Chọn ngày
            </label>
            <input
              type="date"
              className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              onChange={handleDateChange}
              disabled={!selectedCinema}
              min={new Date().toISOString().split("T")[0]}
              max="2030-12-31"
              value={selectedDate}
            />
          </div>
        </div>

        {/* Showtimes */}
        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            <FaTicketAlt className="inline mr-2" />
            Suất chiếu
          </h2>

          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
            </div>
          ) : showtimes.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {showtimes.map((showtime) => {
                let timeString;
                try {
                  // start_time có dạng 'HH:MM:SS' hoặc datetime
                  if (showtime.start_time) {
                    // Nếu là string thời gian thuần (HH:MM:SS)
                    if (typeof showtime.start_time === 'string' && showtime.start_time.includes(':')) {
                      const timeParts = showtime.start_time.split(':');
                      timeString = `${timeParts[0]}:${timeParts[1]}`;
                    } else {
                      // Nếu là datetime đầy đủ
                      const startTime = new Date(showtime.start_time);
                      if (!isNaN(startTime.getTime())) {
                        timeString = startTime.toLocaleTimeString('vi-VN', { 
                          hour: '2-digit', 
                          minute: '2-digit' 
                        });
                      } else {
                        timeString = showtime.start_time;
                      }
                    }
                  } else {
                    timeString = "N/A";
                  }
                } catch (e) {
                  console.error("Lỗi định dạng thời gian:", e, showtime);
                  timeString = showtime.start_time || "N/A";
                }

                return (
                  <button
                    key={showtime.id || showtime.showtime_id}
                    className={`py-3 px-4 rounded-lg border ${
                      selectedShowtime === (showtime.id || showtime.showtime_id)
                        ? "bg-gray-500 text-white border-gray-600"
                        : "bg-white text-gray-800 border-gray-300 hover:bg-gray-100"
                    }`}
                    onClick={() => setSelectedShowtime(showtime.id || showtime.showtime_id)}
                  >
                    <div className="text-center">
                      <div className="font-medium">{timeString}</div>
                      <div className="text-sm mt-1">
                        {showtime.room_name || `Phòng ${showtime.room_id}`}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              {selectedMovie && selectedCinema && selectedDate ? (
                <p>
                  Không có suất chiếu nào cho phim và rạp này vào ngày đã chọn
                </p>
              ) : (
                <p>Vui lòng chọn phim, rạp và ngày để xem suất chiếu</p>
              )}
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="mt-8 flex justify-between">
          <button
            className="bg-gray-300 hover:bg-gray-400 text-gray-800 font-bold py-2 px-4 rounded-lg flex items-center"
            onClick={() => navigate(-1)}
          >
            Quay lại
          </button>

          <button
            className={`bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-lg flex items-center ${
              !selectedShowtime ? "opacity-50 cursor-not-allowed" : ""
            }`}
            onClick={handleNext}
            disabled={!selectedShowtime}
          >
            Tiếp tục
            <FaArrowRight className="ml-2" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default TicketBooking;
