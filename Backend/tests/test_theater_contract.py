import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "Backend"
FRONTEND_ROOT = REPO_ROOT / "Frontend"


def _router_get_paths(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    paths: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "get"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                paths.append(decorator.args[0].value)
    return paths


def test_theater_by_film_route_has_distinct_path():
    paths = _router_get_paths(BACKEND_ROOT / "app" / "router" / "theater.py")

    assert "/by-film/{film_id}" in paths
    assert len(paths) == len(set(paths))


def test_theater_read_schema_matches_jsonb_technologies_shape():
    source = (
        BACKEND_ROOT / "app" / "schemas" / "theater.py"
    ).read_text(encoding="utf-8")

    assert "technologies: Optional[dict] = None" in source
    assert "technologies: List[str] = []" not in source


def test_ticket_booking_uses_api_config_and_distinct_theater_route():
    source = (
        FRONTEND_ROOT / "src" / "components" / "TicketBooking.jsx"
    ).read_text(encoding="utf-8")

    assert "from \"../config/api\"" in source
    assert "http://localhost:8000" not in source
    assert "/theater/${movieId}" not in source
    assert "/theater/by-film/${movieId}" in source


def test_cinema_list_uses_existing_routes_and_api_config():
    source = (
        FRONTEND_ROOT / "src" / "components" / "CinemaList.jsx"
    ).read_text(encoding="utf-8")

    assert "from \"../config/api\"" in source
    assert "http://localhost:8000" not in source
    assert "cinemaDetail" not in source
    assert "/cinema/${cinema.id}/showtimes" not in source
    assert "/TicketBooking" in source
    assert "reviewCount" not in source


def test_api_config_does_not_fallback_to_localhost_in_production():
    source = (
        FRONTEND_ROOT / "src" / "config" / "api.js"
    ).read_text(encoding="utf-8")

    assert "VITE_API_BASE_URL" in source
    assert "VITE_API_PROXY_PATH" in source
    assert "http://localhost:8000" not in source
