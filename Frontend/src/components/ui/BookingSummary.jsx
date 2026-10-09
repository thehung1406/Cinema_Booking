import { CalendarDays, MapPin } from "lucide-react";
import { formatCurrency, formatDate, formatTime } from "../../utils/formatters";
import { Poster } from "./Primitives";

export default function BookingSummary({ booking }) {
  return (
    <section className="surface">
      <div className="flex gap-4">
        <Poster
          src={booking.filmImage}
          title={booking.filmTitle}
          className="!w-20 sm:!w-24 rounded-lg shrink-0 self-start"
        />
        <div className="min-w-0">
          <p className="eyebrow mb-2">
            Đơn vé #{booking.id || booking.bookingId}
          </p>
          <h2 className="text-xl font-bold mb-3">
            {booking.filmTitle || "Tên phim chưa cập nhật"}
          </h2>
          <p className="flex gap-2 text-sm text-gray-600 mb-2">
            <MapPin size={16} className="shrink-0 mt-1" aria-hidden="true" />
            <span>
              {booking.theaterName || "Chưa cập nhật rạp"} ·{" "}
              {booking.roomName || "Chưa cập nhật phòng"}
            </span>
          </p>
          <p className="flex gap-2 text-sm text-gray-600">
            <CalendarDays
              size={16}
              className="shrink-0 mt-1"
              aria-hidden="true"
            />
            <span>
              {formatDate(booking.showDate)} · {formatTime(booking.startTime)}
            </span>
          </p>
        </div>
      </div>
      <div className="border-t border-gray-200 mt-5 pt-5">
        <h3 className="font-semibold mb-3">
          Ghế của bạn {booking.seats?.length ? `(${booking.seats.length})` : ""}
        </h3>
        <div className="flex flex-wrap gap-2">
          {booking.seats?.map((seat, index) => (
            <span
              key={seat.seat_id || index}
              className="text-sm border border-gray-200 bg-gray-50 rounded-lg px-3 py-2"
            >
              <strong>{seat.seat_name || seat.seatName}</strong>
              {seat.seat_type && ` · ${seat.seat_type}`} ·{" "}
              {formatCurrency(seat.price)}
            </span>
          ))}
        </div>
        {!booking.seats?.length && (
          <p className="text-sm text-gray-500">Chưa có thông tin ghế.</p>
        )}
      </div>
      <div className="flex justify-between gap-3 border-t border-gray-200 mt-5 pt-5">
        <span className="font-semibold">Tổng tiền</span>
        <strong className="text-xl text-red-700">
          {formatCurrency(booking.totalAmount)}
        </strong>
      </div>
    </section>
  );
}
