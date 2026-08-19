import React, { useState, useEffect } from "react";
import { FaStar,  FaMapMarkerAlt,  FaTicketAlt } from "react-icons/fa";
import { Link } from "react-router-dom";
import api from "../config/api";

function CinemaList() {
  const [cinemas, setCinemas] = useState([]);
  const [selectedCity, setSelectedCity] = useState("all");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Sử dụng API GET /theater/ để lấy danh sách theaters
        const cinemaRes = await api.get("/theater/");
        setCinemas(cinemaRes.data);
        setLoading(false);
      } catch (error) {
        console.error("Lỗi khi lấy dữ liệu:", error);
        setLoading(false);
      }
    };
    fetchData();
  }, []);
  const filteredCinemas =
    selectedCity === "all"
      ? cinemas
      : cinemas.filter((cinema) => cinema.city === selectedCity);
  const cities = ["all", ...new Set(cinemas.map((cinema) => cinema.city))];


  return (
    <div className="bg-gray-100 min-h-screen">
      {/* Banner */}
      <div className="relative h-64 bg-cover bg-center">
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <h2 className="text-4xl font-bold text-white">HỆ THỐNG RẠP CGV</h2>
        </div>
      </div>
      {/* Filter Section */}
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h3 className="text-xl font-semibold mb-4">Tìm rạp CGV</h3>
          <div className="flex flex-wrap gap-4">
            <div className="w-full md:w-1/3">
              <label className="block text-gray-700 mb-2">
                Chọn thành phố:
              </label>
              <select
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
                value={selectedCity}
                onChange={(e) => setSelectedCity(e.target.value)}
              >
                {cities.map((city) => (
                  <option key={city} value={city}>{city === "all" ? "Tất cả thành phố" : city}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
        {/* Cinema List */}
        <div className="mb-8">
          <h3 className="text-2xl font-bold mb-6">
            Danh sách rạp CGV{" "}
            {selectedCity !== "all" ? `tại ${selectedCity}` : ""}
          </h3>
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-red-700"></div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCinemas.map((cinema) => (
                <CinemaCard key={cinema.id} cinema={cinema} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
// Component Card cho mỗi rạp chiếu
function CinemaCard({ cinema }) {
  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300">
      <div className="relative h-48 overflow-hidden">
        <img
          src={cinema.image}
          alt={cinema.name}
          className="w-full h-full object-cover transition-transform duration-300 hover:scale-110"
        />
        {cinema.special && (
          <div className="absolute top-0 right-0 bg-yellow-500 text-white px-3 py-1 text-sm font-bold">
            {cinema.special}
          </div>
        )}
      </div>
      <div className="p-5">
        <h4 className="text-xl font-bold mb-2 text-red-700">{cinema.name}</h4>
        <div className="flex items-center mb-3">
          <FaMapMarkerAlt className="text-gray-500 mr-2" />
          <p className="text-gray-600 text-sm">{cinema.address}</p>
        </div>
        <div className="flex items-center mb-3">
          <FaStar className="text-yellow-500 mr-2" />
          <p className="text-gray-700">
            {cinema.rating ? `${cinema.rating}/5` : "Chưa có đánh giá"}
          </p>
        </div>
        <div className="mb-4">
        </div>
        <div className="flex space-x-2">
          <Link
            to={`/TicketBooking?theaterId=${cinema.id}`}
            className="flex-1 bg-red-700 hover:bg-red-800 text-white text-center py-2 px-4 rounded-lg font-semibold flex items-center justify-center"
          >
            <FaTicketAlt className="mr-2" /> Đặt vé
          </Link>
        </div>
      </div>
    </div>
  );
}
export default CinemaList;
