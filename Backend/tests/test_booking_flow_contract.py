from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPO_ROOT / "Frontend" / "src"


def test_ticket_booking_reads_query_params():
    """Kiểm tra TicketBooking.jsx sử dụng useSearchParams để lấy filmId và theaterId."""
    source = (FRONTEND_ROOT / "components" / "TicketBooking.jsx").read_text(encoding="utf-8")
    
    assert "useSearchParams" in source
    assert "searchParams.get" in source
    assert "filmId" in source
    assert "theaterId" in source
    assert "/theater/by-film/" in source


def test_home_page_passes_film_id_to_booking():
    """Kiểm tra MainHomePage.jsx truyền filmId khi bấm Đặt vé và dùng Link thay cho thẻ a."""
    source = (FRONTEND_ROOT / "components" / "MainHomePage.jsx").read_text(encoding="utf-8")
    
    assert "filmId=" in source
    assert "handleBooking(e, movie.id)" in source
    assert '<a href="movie"' not in source
    assert 'href="movie"' not in source
    assert '<Link' in source


def test_movie_pages_pass_film_id_to_booking():
    """Kiểm tra Movie.jsx và MovieDetail.jsx giữ ngữ cảnh filmId khi điều hướng Đặt vé."""
    movie_source = (FRONTEND_ROOT / "components" / "Movie.jsx").read_text(encoding="utf-8")
    detail_source = (FRONTEND_ROOT / "components" / "MovieDetail.jsx").read_text(encoding="utf-8")
    
    assert "filmId=" in movie_source
    assert "handleBooking(e, movie.id)" in movie_source
    
    assert "filmId=" in detail_source
    assert "targetFilmId" in detail_source or "movieId || movie?.id" in detail_source or "filmId=" in detail_source


def test_app_router_has_standard_routes():
    """Kiểm tra App.jsx có các route chuẩn hóa lowercase/kebab-case."""
    source = (FRONTEND_ROOT / "App.jsx").read_text(encoding="utf-8")
    
    assert 'path="ticket-booking"' in source
    assert 'path="movie/:id"' in source
    assert 'path="user-info"' in source
    assert 'path="login"' in source
