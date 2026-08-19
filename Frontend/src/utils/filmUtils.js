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
  const today = new Date(referenceDate);
  const releaseDate = new Date(movie.release_date);
  const endDate = movie.end_date
    ? new Date(movie.end_date)
    : new Date(releaseDate.getTime() + 90 * 24 * 60 * 60 * 1000); // Mặc định 90 ngày nếu không có end_date

  return today >= releaseDate && today <= endDate;
};

/**
 * Format ngày phát hành theo định dạng ngày/tháng/năm
 * @param {string|Date} dateString - Chuỗi ngày
 * @param {string} [locale='vi-VN'] - Mã ngôn ngữ
 * @returns {string} Chuỗi ngày đã format
 */
export const formatReleaseDate = (dateString, locale = 'vi-VN') => {
  if (!dateString) return 'Chưa xác định';
  const options = { day: '2-digit', month: '2-digit', year: 'numeric' };
  return new Date(dateString).toLocaleDateString(locale, options);
};

/**
 * Format ngày chi tiết (ngày DD tháng MM, YYYY)
 * @param {string|Date} dateString - Chuỗi ngày
 * @param {string} [locale='vi-VN'] - Mã ngôn ngữ
 * @returns {string} Chuỗi ngày chi tiết
 */
export const formatDetailDate = (dateString, locale = 'vi-VN') => {
  if (!dateString) return 'Chưa xác định';
  const date = new Date(dateString);
  return date.toLocaleDateString(locale, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
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
    } else {
      upcoming.push(movie);
    }
  }

  return { nowShowing, upcoming };
};
