import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

export default function EditorialMoment() {
  const root = useRef(null);
  useEffect(() => {
    let active = true, animation;
    const element = root.current;
    const base = "/assets/taste/moments/";
    Promise.all([
      import(/* @vite-ignore */ `${base}word-highlight/moment.js`),
      import(/* @vite-ignore */ `${base}lib.js`),
    ]).then(([moment, lib]) => {
      if (active) { animation = moment.default(element, {}, lib); element.dataset.momentMounted = "1"; }
    }).catch(() => { /* The statement stays readable if its optional motion cannot load. */ });
    return () => { active = false; animation?.destroy?.(); delete element.dataset.momentMounted; };
  }, []);
  return <section ref={root} className="editorial-moment" data-moment="word-highlight">
    <div className="shell"><p className="mo-wh__text">Từ <strong>bộ phim bạn chọn</strong> đến <strong>chỗ ngồi của bạn.</strong> Xem lịch chiếu, chọn ghế và theo dõi đơn vé tại CGV.</p><Link className="btn btn-secondary mt-8" to="/ticket-booking">Chọn lịch chiếu</Link></div>
  </section>;
}
