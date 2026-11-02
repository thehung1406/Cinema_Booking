"""Web routing/payment contracts, independent of all server implementations."""

from pathlib import Path

FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "apps/web/src"


def test_ticket_booking_reads_query_params():
    """Kiểm tra TicketBooking.jsx sử dụng useSearchParams để lấy filmId và theaterId."""
    source = (FRONTEND_ROOT / "components" / "TicketBooking.jsx").read_text(
        encoding="utf-8"
    )

    assert "useSearchParams" in source
    assert 'params.get("filmId")' in source and 'params.get("theaterId")' in source
    assert "filmId" in source
    assert "theaterId" in source
    assert "/theaters/by-film/" in source


def test_home_page_passes_film_id_to_booking():
    """Kiểm tra MainHomePage.jsx truyền filmId khi bấm Đặt vé và dùng Link thay cho thẻ a."""
    source = (FRONTEND_ROOT / "components" / "MainHomePage.jsx").read_text(
        encoding="utf-8"
    )

    assert "filmId=" in source
    card = (FRONTEND_ROOT / "components/ui/MovieCard.jsx").read_text(encoding="utf-8")
    assert "filmId=${movie.id}" in card and "<MovieCard" in source
    assert '<a href="movie"' not in source
    assert 'href="movie"' not in source
    assert "<Link" in source


def test_movie_pages_pass_film_id_to_booking():
    """Kiểm tra Movie.jsx và MovieDetail.jsx giữ ngữ cảnh filmId khi điều hướng Đặt vé."""
    movie_source = (FRONTEND_ROOT / "components" / "Movie.jsx").read_text(
        encoding="utf-8"
    )
    detail_source = (FRONTEND_ROOT / "components" / "MovieDetail.jsx").read_text(
        encoding="utf-8"
    )

    card = (FRONTEND_ROOT / "components/ui/MovieCard.jsx").read_text(encoding="utf-8")
    assert "<MovieCard" in movie_source and "filmId=${movie.id}" in card

    assert "filmId=" in detail_source
    assert (
        "targetFilmId" in detail_source
        or "movieId || movie?.id" in detail_source
        or "filmId=" in detail_source
    )


def test_app_router_has_standard_routes():
    """Kiểm tra App.jsx có các route chuẩn hóa lowercase/kebab-case."""
    source = (FRONTEND_ROOT / "App.jsx").read_text(encoding="utf-8")

    assert 'path="ticket-booking"' in source
    assert 'path="movie/:id"' in source
    assert 'path="user-info"' in source
    assert 'path="login"' in source


def test_no_n_plus_one_in_main_home_page():
    """Kiểm tra MainHomePage.jsx không còn gọi detail endpoint theo từng phim (loại bỏ N+1)."""
    source = (FRONTEND_ROOT / "components" / "MainHomePage.jsx").read_text(
        encoding="utf-8"
    )

    # Không còn pattern Promise.all map từng film gọi endpoint detail
    assert "films/${film.id}" not in source
    hook = (FRONTEND_ROOT / "hooks/useFilms.js").read_text(encoding="utf-8")
    assert "useFilms()" in source and "filmService.getFilms()" in hook
    assert "Promise.all" not in hook
    assert "classifyMovies" in source


def test_no_n_plus_one_in_movie_page():
    """Kiểm tra Movie.jsx không còn gọi detail endpoint theo từng phim (loại bỏ N+1)."""
    source = (FRONTEND_ROOT / "components" / "Movie.jsx").read_text(encoding="utf-8")

    assert "films/${film.id}" not in source
    hook = (FRONTEND_ROOT / "hooks/useFilms.js").read_text(encoding="utf-8")
    assert "useFilms()" in source and "filmService.getFilms()" in hook
    assert "Promise.all" not in hook
    assert "isNowShowing" in source


def test_film_service_and_utils_exist():
    """Kiểm tra filmService và filmUtils đã được tạo đầy đủ."""
    service_file = FRONTEND_ROOT / "services" / "filmService.js"
    utils_file = FRONTEND_ROOT / "utils" / "filmUtils.js"

    assert service_file.exists(), "apps/web/src/services/filmService.js must exist"
    assert utils_file.exists(), "apps/web/src/utils/filmUtils.js must exist"

    service_src = service_file.read_text(encoding="utf-8")
    assert "getFilms" in service_src
    assert "getFilmDetail" in service_src

    utils_src = utils_file.read_text(encoding="utf-8")
    assert "isNowShowing" in utils_src
    assert "classifyMovies" in utils_src
    assert "formatReleaseDate" in utils_src


def test_frontend_payment_components_contract():
    """Kiểm tra các component Frontend PaymentPage và VNPayReturn."""
    payment_page_src = (FRONTEND_ROOT / "components" / "PaymentPage.jsx").read_text(
        encoding="utf-8"
    )
    vnpay_return_src = (FRONTEND_ROOT / "components" / "VNPayReturn.jsx").read_text(
        encoding="utf-8"
    )
    app_src = (FRONTEND_ROOT / "App.jsx").read_text(encoding="utf-8")

    # PaymentPage checks
    assert "/payment/vnpay-url" in payment_page_src
    assert "bookingId" in payment_page_src
    assert "/payment-result" in payment_page_src
    assert "Thanh toán qua VNPay" in payment_page_src
    assert "mayPay(payment, booking)" in payment_page_src
    assert "payment/status/" in payment_page_src
    assert "secondsLeft" not in payment_page_src

    # VNPayReturn checks
    assert "/payment/vnpay-return" in vnpay_return_src
    assert "params.vnp_SecureHash" in vnpay_return_src
    assert "paymentStage(data)" in vnpay_return_src
    assert "QRCode" in vnpay_return_src
    assert (
        "ticket.ticket_code" in vnpay_return_src
        and "/tickets/booking/" in vnpay_return_src
    )
    assert "value={JSON.stringify" not in vnpay_return_src
    assert "Thanh toán thành công" in vnpay_return_src
    assert "location.state?.booking" not in vnpay_return_src
    assert "/bookings/" in vnpay_return_src

    # App.jsx routing checks
    assert 'path="payment/:bookingId"' in app_src
    assert 'path="payment-result"' in app_src


def test_ticket_booking_uses_api_config_and_distinct_theater_route():
    source = (FRONTEND_ROOT / "components" / "TicketBooking.jsx").read_text(
        encoding="utf-8"
    )

    assert 'from "../config/api"' in source
    assert "http://localhost:8000" not in source
    assert "/theater/${movieId}" not in source
    assert "/theaters/by-film/${movieId}" in source


def test_cinema_list_uses_existing_routes_and_api_config():
    source = (FRONTEND_ROOT / "components" / "CinemaList.jsx").read_text(
        encoding="utf-8"
    )

    assert 'from "../config/api"' in source
    assert "http://localhost:8000" not in source
    assert "cinemaDetail" not in source
    assert "/cinema/${cinema.id}/showtimes" not in source
    assert "/TicketBooking" in source
    assert "reviewCount" not in source


def test_api_config_does_not_fallback_to_localhost_in_production():
    source = (FRONTEND_ROOT / "config" / "api.js").read_text(encoding="utf-8")

    assert "VITE_API_BASE_URL" in source
    assert "VITE_API_PROXY_PATH" in source
    assert "http://localhost:8000" not in source
