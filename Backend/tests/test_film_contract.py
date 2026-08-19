from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "Backend"
FRONTEND_ROOT = REPO_ROOT / "Frontend" / "src"


def test_film_read_schema_has_list_and_filter_fields():
    """Kiểm tra FilmRead schema chứa đầy đủ các trường để hiển thị card và phân loại phim."""
    source = (BACKEND_ROOT / "app" / "schemas" / "film.py").read_text(encoding="utf-8")
    
    assert "class FilmRead(SQLModel):" in source
    assert "language: Optional[str]" in source
    assert "subtitle: Optional[str]" in source
    assert "release_date: Optional[date]" in source
    assert "end_date: Optional[date]" in source


def test_no_n_plus_one_in_main_home_page():
    """Kiểm tra MainHomePage.jsx không còn gọi detail endpoint theo từng phim (loại bỏ N+1)."""
    source = (FRONTEND_ROOT / "components" / "MainHomePage.jsx").read_text(encoding="utf-8")
    
    # Không còn pattern Promise.all map từng film gọi endpoint detail
    assert "films/${film.id}" not in source
    assert "filmService" in source
    assert "classifyMovies" in source


def test_no_n_plus_one_in_movie_page():
    """Kiểm tra Movie.jsx không còn gọi detail endpoint theo từng phim (loại bỏ N+1)."""
    source = (FRONTEND_ROOT / "components" / "Movie.jsx").read_text(encoding="utf-8")
    
    assert "films/${film.id}" not in source
    assert "filmService" in source
    assert "isNowShowing" in source


def test_film_service_and_utils_exist():
    """Kiểm tra filmService và filmUtils đã được tạo đầy đủ."""
    service_file = FRONTEND_ROOT / "services" / "filmService.js"
    utils_file = FRONTEND_ROOT / "utils" / "filmUtils.js"
    
    assert service_file.exists(), "Frontend/src/services/filmService.js must exist"
    assert utils_file.exists(), "Frontend/src/utils/filmUtils.js must exist"
    
    service_src = service_file.read_text(encoding="utf-8")
    assert "getFilms" in service_src
    assert "getFilmDetail" in service_src
    
    utils_src = utils_file.read_text(encoding="utf-8")
    assert "isNowShowing" in utils_src
    assert "classifyMovies" in utils_src
    assert "formatReleaseDate" in utils_src
