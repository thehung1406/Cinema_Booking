def validate_context(reader, context):
    reader.names(context)


def run_tool(reader, call, evening=False):
    return reader.run(call, evening)


def missing_fields(call):
    required = {
        "search_films": (), "get_showtimes": ("film_id", "theater_id", "show_date"),
        "get_positive_films": ("theater_id", "show_date"),
        "get_ticket_prices": ("showtime_id",), "get_seat_availability": ("showtime_id",),
    }[call.name]
    return [field for field in required if getattr(call.context, field) is None]
