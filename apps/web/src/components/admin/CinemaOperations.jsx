import { useEffect, useRef, useState } from "react";
import api from "../../config/api";
import { errorText } from "./adminData";

export default function CinemaOperations({ permissions }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const known = useRef(new Map());
  const allowed = permissions.some((p) => ["rooms.manage", "showtimes.manage", "seat_types.manage"].includes(p));
  useEffect(() => {
    if (!allowed) return;
    let active = true;
    let running = false;
    const controller = new AbortController();
    const load = async () => {
      if (running) return;
      running = true;
      try {
        const { data } = await api.get("/admin/cinema-operations", { signal: controller.signal });
        if (!active) return;
        for (const item of data.items) {
          if (known.current.has(item.operation_id) && known.current.get(item.operation_id) !== item.status && ["DONE", "FAILED"].includes(item.status)) {
            window.dispatchEvent(new Event("cinema-operation-updated"));
          }
          known.current.set(item.operation_id, item.status);
        }
        setItems(data.items.filter((item) => item.status !== "DONE").slice(0, 10));
        setError("");
      } catch (err) {
        if (active && err.code !== "ERR_CANCELED") setError(errorText(err));
      } finally { running = false; }
    };
    load();
    const timer = setInterval(load, 3000);
    window.addEventListener("cinema-operation-submitted", load);
    return () => {
      active = false; controller.abort(); clearInterval(timer);
      window.removeEventListener("cinema-operation-submitted", load);
    };
  }, [allowed]);
  if (!allowed || (!items.length && !error)) return null;
  return <section className="admin-panel" aria-label="Tác vụ cấu hình rạp">
    <h2>Tác vụ cấu hình rạp</h2>
    {error && <p role="alert" className="admin-error">{error}</p>}
    {items.map((item) => <p key={item.operation_id} role="status" className={item.status === "FAILED" ? "admin-error" : "admin-notice"}>
      Phòng #{item.room_id} · {item.status}: {item.message}
      {item.status === "FAILED" && " Kiểm tra lại cấu hình; dùng Mở nhận hold trên lịch chiếu khi cấu hình hiện tại có thể bán."}
    </p>)}
  </section>;
}
