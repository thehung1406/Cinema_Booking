import api from '../config/api';

/**
 * Service quản lý các API liên quan đến phim
 */
export const filmService = {
  /**
   * Lấy danh sách phim
   * @param {Object} params - Query params (ví dụ: { now_showing: true })
   * @returns {Promise<Array>} Danh sách phim
   */
  async getFilms(params = {}) {
    const response = await api.get('/films/', { params });
    return response.data;
  },

  /**
   * Lấy chi tiết một bộ phim theo ID
   * @param {string|number} id - Film ID
   * @returns {Promise<Object>} Thông tin chi tiết phim
   */
  async getFilmDetail(id) {
    const response = await api.get(`/films/${id}`);
    return response.data;
  },

  /**
   * Lấy danh sách phim đang chiếu từ backend
   * @returns {Promise<Array>} Danh sách phim đang chiếu
   */
  async getNowShowingFilms() {
    return this.getFilms({ now_showing: true });
  },
};

export default filmService;
