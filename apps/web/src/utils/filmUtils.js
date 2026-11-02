import { localDateInput } from "./formatters.js";

/**
 * Tiện ích xử lý dữ liệu phim dùng chung giữa các component
 */

/**
 * Kiểm tra xem một phim có đang được chiếu không dựa vào release_date và end_date
 * @param {Object} movie - Đối tượng phim
 * @param {Date} [referenceDate=new Date()] - Ngày mốc so sánh
 * @returns {boolean} True nếu phim đang chiếu
 */
export const isNowShowing = (movie, referenceDate = new Date()) => {
  if (!movie || !movie.release_date) return false;
  const today = localDateInput(referenceDate);
  const releaseDate = String(movie.release_date).slice(0, 10);
  const endDate = movie.end_date ? String(movie.end_date).slice(0, 10) : null;
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(releaseDate) &&
    today >= releaseDate &&
    (!endDate || today <= endDate)
  );
};

export const isUpcoming = (movie, referenceDate = new Date()) =>
  Boolean(movie?.release_date) &&
  String(movie.release_date).slice(0, 10) > localDateInput(referenceDate);

/**
 * Format ngày phát hành theo định dạng ngày/tháng/năm
 * @param {string|Date} dateString - Chuỗi ngày
 * @param {string} [locale='vi-VN'] - Mã ngôn ngữ
 * @returns {string} Chuỗi ngày đã format
 */
export const formatReleaseDate = (dateString, locale = "vi-VN") => {
  if (!dateString) return "Chưa xác định";
  const options = { day: "2-digit", month: "2-digit", year: "numeric" };
  return new Date(dateString).toLocaleDateString(locale, options);
};

/**
 * Format ngày chi tiết (ngày DD tháng MM, YYYY)
 * @param {string|Date} dateString - Chuỗi ngày
 * @param {string} [locale='vi-VN'] - Mã ngôn ngữ
 * @returns {string} Chuỗi ngày chi tiết
 */
export const formatDetailDate = (dateString, locale = "vi-VN") => {
  if (!dateString) return "Chưa xác định";
  const date = new Date(dateString);
  return date.toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
};

/**
 * Phân loại danh sách phim thành đang chiếu và sắp chiếu
 * @param {Array} movies - Danh sách phim
 * @returns {{ nowShowing: Array, upcoming: Array }}
 */
export const classifyMovies = (movies = []) => {
  const nowShowing = [];
  const upcoming = [];

  for (const movie of movies) {
    if (isNowShowing(movie)) {
      nowShowing.push(movie);
    } else if (isUpcoming(movie)) {
      upcoming.push(movie);
    }
  }

  return { nowShowing, upcoming };
};
