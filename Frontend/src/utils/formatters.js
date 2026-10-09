const zone = "Asia/Ho_Chi_Minh";
export function formatCurrency(value) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    !Number.isFinite(Number(value))
  )
    return "Chưa có giá";
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  }).format(Number(value));
}
export function formatDate(value) {
  if (!value) return "Chưa xác định";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Chưa xác định"
    : date.toLocaleDateString("vi-VN", {
        timeZone: zone,
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
}
export function formatTime(value) {
  if (!value) return "Chưa xác định";
  if (/^\d{2}:\d{2}(:\d{2})?$/.test(value)) return value.slice(0, 5);
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Chưa xác định"
    : date.toLocaleTimeString("vi-VN", {
        timeZone: zone,
        hour: "2-digit",
        minute: "2-digit",
      });
}
export function localDateInput(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
export function paymentState(booking) {
  if (booking?.paymentStatus === "PAID") return "success";
  if (
    ["FAILED", "CANCELLED"].includes(booking?.paymentStatus) ||
    ["CANCELLED", "EXPIRED"].includes(booking?.bookingStatus)
  )
    return "failed";
  return "pending";
}
