import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../../config/api";
import { formatCurrency, formatDate, localDateInput } from "../../utils/formatters";
import { ConfirmAction, DataTable, Editor, Field, MultiChoice, PageHeading, Pagination } from "./AdminShared";
import { useAdminData } from "./adminData";

const lookup = (items, id) => items?.find((item) => item.id === Number(id));
const numbers = (value, keys) => ({ ...value, ...Object.fromEntries(keys.map((key) => [key, Number(value[key])])) });
const pick = (item, defaults) => Object.fromEntries(Object.entries(defaults).map(([key, value]) => [key, item?.[key] ?? value]));
const options = (items, label = "name") => items?.map((item) => <option key={item.id} value={item.id}>{item[label]}</option>);

function EntityPage({ resource, title, description, createLabel, columns, defaults, prepare = (value) => value, fields, filters, actions, searchable = true }) {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [extra, setExtra] = useState({});
  const [editor, setEditor] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [notice, setNotice] = useState("");
  const catalog = useAdminData("/admin/catalog");
  const list = useAdminData(`/admin/${resource}`, { ...(searchable ? { q: query } : {}), ...extra, offset, limit: 20 });
  const data = catalog.data || {};
  const refresh = () => { list.reload(); catalog.reload(); setNotice("Đã lưu thay đổi."); };
  return <>
    <PageHeading title={title} description={description} createLabel={createLabel} onCreate={() => setEditor({})} />
    {notice && <p role="status" className="admin-notice">{notice}</p>}
    <section className="admin-panel" aria-label={title}>
      <div className="admin-toolbar">{searchable && <Field type="search" label="Tìm kiếm" placeholder="Nhập tên để tìm…" value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0); }} />}
        {filters?.(extra, (key, value) => { setExtra((old) => ({ ...old, [key]: value || undefined })); setOffset(0); }, data)}
      </div>
      <DataTable columns={columns(data)} rows={list.data?.items} loading={list.loading || catalog.loading}
        error={list.error || catalog.error} reload={() => { list.reload(); catalog.reload(); }} actions={(row) => <>
          {actions?.(row)}<button onClick={() => setEditor(row)}>Sửa</button>
          <button className="admin-danger" onClick={() => setDeleting(row)}>Xóa</button></>} />
      <Pagination total={list.data?.total} offset={offset} onChange={setOffset} />
    </section>
    {editor && <Editor title={editor.id ? `Cập nhật ${title.toLowerCase()}` : createLabel} initial={pick(editor, defaults(data))}
      onClose={() => setEditor(null)} onSave={async (value) => {
        await api[editor.id ? "put" : "post"](`/admin/${resource}${editor.id ? `/${editor.id}` : ""}`, prepare(value));
        refresh();
      }}>{(value, set, setValue) => fields(value, set, setValue, data, editor)}</Editor>}
    {deleting && <ConfirmAction title="Xác nhận xóa" description={`Xóa ${deleting.title || deleting.name || "suất chiếu này"}? Dữ liệu đang được sử dụng sẽ được hệ thống bảo vệ.`}
      onClose={() => setDeleting(null)} onConfirm={async () => {
        await api.delete(`/admin/${resource}/${deleting.id}`);
        setOffset(0); refresh(); setNotice("Đã xóa thành công.");
      }} />}
  </>;
}

export function FilmsPage() {
  return <EntityPage resource="films" title="Quản lý phim" createLabel="Thêm phim" description="Quản lý nội dung, thể loại, định dạng và thời gian phát hành phim."
    columns={(catalog) => [
      { key: "title", label: "Phim", render: (row) => <>{row.title}<small>{row.rating || "Chưa phân loại"} · {row.language || "Chưa có ngôn ngữ"}</small></> },
      { key: "duration_minutes", label: "Thời lượng", render: (row) => `${row.duration_minutes || "—"} phút` },
      { key: "genre_ids", label: "Thể loại", render: (row) => row.genre_ids.map((id) => lookup(catalog.genres, id)?.name).join(", ") },
      { key: "release_date", label: "Thời gian phát hành", render: (row) => <>{formatDate(row.release_date)}<small>đến {formatDate(row.end_date)}</small></> },
    ]}
    defaults={() => ({ title: "", duration_minutes: 120, release_date: localDateInput(), end_date: localDateInput(), genre_ids: [], format_ids: [], image: "", rating: "T13", language: "Tiếng Việt", subtitle: "", description: "", trailer: "" })}
    prepare={(value) => numbers(value, ["duration_minutes"])}
    fields={(value, set, setValue, catalog) => <>
      <Field label="Tên phim *" required maxLength={100} value={value.title} onChange={set("title")} />
      <div className="admin-form-grid"><Field label="Thời lượng (phút) *" required type="number" min={1} max={600} value={value.duration_minutes} onChange={set("duration_minutes")} />
        <Field label="Phân loại độ tuổi" maxLength={10} value={value.rating} onChange={set("rating")} />
        <Field label="Ngày khởi chiếu *" required type="date" value={value.release_date} onChange={set("release_date")} />
        <Field label="Ngày kết thúc *" required type="date" min={value.release_date} value={value.end_date} onChange={set("end_date")} />
        <Field label="Ngôn ngữ" maxLength={50} value={value.language} onChange={set("language")} />
        <Field label="Phụ đề" maxLength={50} value={value.subtitle} onChange={set("subtitle")} /></div>
      <MultiChoice label="Thể loại *" items={catalog.genres || []} value={value.genre_ids} onChange={(ids) => setValue((old) => ({ ...old, genre_ids: ids }))} />
      <MultiChoice label="Định dạng *" items={catalog.formats || []} value={value.format_ids} onChange={(ids) => setValue((old) => ({ ...old, format_ids: ids }))} />
      <Field label="Đường dẫn ảnh poster" maxLength={255} value={value.image} onChange={set("image")} />
      <Field label="Đường dẫn trailer" maxLength={255} value={value.trailer} onChange={set("trailer")} />
      <Field label="Nội dung phim" type="textarea" maxLength={20000} value={value.description} onChange={set("description")} />
    </>} />;
}

export function RoomsPage() {
  return <EntityPage resource="rooms" title="Phòng chiếu & ghế" createLabel="Thêm phòng chiếu" description="Thiết lập phòng chiếu, sức chứa và sơ đồ ghế tại từng rạp."
    columns={(catalog) => [
      { key: "name", label: "Phòng chiếu" },
      { key: "theater_id", label: "Rạp", render: (row) => lookup(catalog.theaters, row.theater_id)?.name || "—" },
      { key: "capacity", label: "Sức chứa", render: (row) => `${row.capacity} ghế` },
      { key: "room_type", label: "Loại phòng" },
      { key: "status", label: "Trạng thái", render: (row) => <span className={`admin-badge ${row.status === "ACTIVE" ? "success" : "pending"}`}>{row.status === "ACTIVE" ? "Hoạt động" : "Bảo trì"}</span> },
    ]}
    actions={(row) => <Link to={`/admin/rooms/${row.id}/seats`}>Sơ đồ ghế</Link>}
    filters={(extra, set, catalog) => <Field label="Rạp" value={extra.theater_id || ""} onChange={(event) => set("theater_id", event.target.value)}><option value="">Tất cả rạp</option>{options(catalog.theaters)}</Field>}
    defaults={() => ({ theater_id: "", name: "", capacity: 100, room_type: "2D", status: "ACTIVE" })}
    prepare={(value) => numbers(value, ["theater_id", "capacity"])}
    fields={(value, set, _setValue, catalog) => <>
      <Field label="Rạp *" required value={value.theater_id} onChange={set("theater_id")}><option value="">Chọn rạp</option>{options(catalog.theaters)}</Field>
      <Field label="Tên phòng *" required maxLength={50} value={value.name} onChange={set("name")} />
      <div className="admin-form-grid"><Field label="Sức chứa *" required type="number" min={1} max={2000} value={value.capacity} onChange={set("capacity")} />
        <Field label="Loại phòng" maxLength={50} value={value.room_type} onChange={set("room_type")} /></div>
      <Field label="Trạng thái" value={value.status} onChange={set("status")}><option value="ACTIVE">Hoạt động</option><option value="MAINTENANCE">Bảo trì</option></Field>
    </>} />;
}

export function ShowtimesPage() {
  return <EntityPage resource="showtimes" title="Quản lý lịch chiếu" createLabel="Thêm suất chiếu" searchable={false}
    description="Lập lịch theo phim, phòng và định dạng. Giờ chiếu theo múi giờ Việt Nam, kết thúc trong cùng ngày."
    columns={(catalog) => [
      { key: "film_id", label: "Phim", render: (row) => lookup(catalog.films, row.film_id)?.title || `Phim #${row.film_id}` },
      { key: "room_id", label: "Phòng / rạp", render: (row) => {
        const room = lookup(catalog.rooms, row.room_id);
        return <>{room?.name || `Phòng #${row.room_id}`}<small>{lookup(catalog.theaters, room?.theater_id)?.name}</small></>;
      } },
      { key: "show_date", label: "Ngày chiếu", render: (row) => formatDate(row.show_date) },
      { key: "start_time", label: "Giờ chiếu", render: (row) => `${row.start_time.slice(0, 5)} – ${row.end_time.slice(0, 5)}` },
      { key: "format_id", label: "Định dạng", render: (row) => lookup(catalog.formats, row.format_id)?.name },
      { key: "status", label: "Trạng thái", render: (row) => <span className="admin-badge">{{ ACTIVE: "Đang mở", COMPLETED: "Hoàn tất", CANCELLED: "Đã hủy" }[row.status] || row.status}</span> },
    ]}
    filters={(extra, set, catalog) => <>
      <Field label="Phim" value={extra.film_id || ""} onChange={(event) => set("film_id", event.target.value)}><option value="">Tất cả phim</option>{options(catalog.films, "title")}</Field>
      <Field label="Phòng chiếu" value={extra.room_id || ""} onChange={(event) => set("room_id", event.target.value)}><option value="">Tất cả phòng</option>{options(catalog.rooms)}</Field>
      <Field label="Ngày chiếu" type="date" value={extra.show_date || ""} onChange={(event) => set("show_date", event.target.value)} /></>}
    defaults={() => ({ film_id: "", room_id: "", format_id: "", show_date: localDateInput(new Date(Date.now() + 86400000)), start_time: "18:00", end_time: "20:00" })}
    prepare={(value) => numbers(value, ["film_id", "room_id", "format_id"])}
    fields={(value, set, setValue, catalog) => <>
      <Field label="Phim *" required value={value.film_id} onChange={(event) => setValue((old) => ({ ...old, film_id: event.target.value, format_id: "" }))}><option value="">Chọn phim</option>{options(catalog.films, "title")}</Field>
      <Field label="Phòng chiếu *" required value={value.room_id} onChange={set("room_id")}><option value="">Chọn phòng</option>{catalog.rooms?.filter((room) => room.status === "ACTIVE").map((room) => <option key={room.id} value={room.id}>{lookup(catalog.theaters, room.theater_id)?.name} · {room.name}</option>)}</Field>
      <div className="admin-form-grid"><Field label="Ngày chiếu *" required type="date" min={localDateInput()} value={value.show_date} onChange={set("show_date")} />
        <Field label="Định dạng *" required value={value.format_id} onChange={set("format_id")}><option value="">Chọn định dạng</option>{options(catalog.formats?.filter((format) => lookup(catalog.films, value.film_id)?.format_ids.includes(format.id)))}</Field>
        <Field label="Giờ bắt đầu *" required type="time" value={value.start_time} onChange={set("start_time")} />
        <Field label="Giờ kết thúc *" required type="time" value={value.end_time} onChange={set("end_time")} /></div>
    </>} />;
}

export function PricesPage() {
  return <EntityPage resource="prices" title="Quản lý giá vé" createLabel="Thêm loại ghế & giá" description="Giá hiện hành theo loại ghế của từng phòng. Giá đã chốt trong đơn đặt vé được giữ nguyên."
    columns={(catalog) => [
      { key: "name", label: "Loại ghế" },
      { key: "room_id", label: "Phòng / rạp", render: (row) => {
        const room = lookup(catalog.rooms, row.room_id);
        return <>{room?.name}<small>{lookup(catalog.theaters, room?.theater_id)?.name}</small></>;
      } },
      { key: "base_price", label: "Giá hiện hành", render: (row) => formatCurrency(row.base_price) },
    ]}
    filters={(extra, set, catalog) => <Field label="Phòng chiếu" value={extra.room_id || ""} onChange={(event) => set("room_id", event.target.value)}><option value="">Tất cả phòng</option>{options(catalog.rooms)}</Field>}
    defaults={() => ({ room_id: "", name: "", base_price: 75000 })}
    prepare={(value) => numbers(value, ["room_id"])}
    fields={(value, set, _setValue, catalog, editor) => <>
      <Field label="Phòng chiếu *" required disabled={!!editor.id} value={value.room_id} onChange={set("room_id")}><option value="">Chọn phòng</option>{options(catalog.rooms)}</Field>
      <Field label="Tên loại ghế *" required maxLength={30} value={value.name} onChange={set("name")} />
      <Field label="Giá vé (VNĐ) *" required type="number" min={0} max={9999999999.99} step="0.01" value={value.base_price} onChange={set("base_price")} />
    </>} />;
}

export function SeatsPage() {
  const { roomId } = useParams();
  const [editor, setEditor] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");
  const list = useAdminData(`/admin/rooms/${roomId}/seats`);
  const data = list.data;
  const seats = data?.seats.filter((seat) => seat.seat_name.toLowerCase().includes(search.toLowerCase())) || [];
  const rows = [...new Set(seats.map((seat) => seat.seat_name.replace(/\d+$/, "")))].sort();
  return <>
    <Link to="/admin/rooms">← Danh sách phòng chiếu</Link>
    <PageHeading title={`Sơ đồ ghế · ${data?.room.name || "Phòng chiếu"}`} description={data ? `${data.seats.length} / ${data.room.capacity} ghế đã bố trí. Chọn một ghế để sửa thông tin.` : "Quản lý vị trí và loại ghế."} createLabel="Thêm ghế" onCreate={data ? () => setEditor({}) : undefined} />
    {notice && <p role="status" className="admin-notice">{notice}</p>}
    <section className="admin-panel">
      {!data?.seat_types.length && data && <p className="admin-error">Phòng chưa có loại ghế. <Link to="/admin/prices">Tạo loại ghế và giá vé</Link> trước khi thêm ghế.</p>}
      <Field label="Tìm ghế" type="search" placeholder="Ví dụ: A1" value={search} onChange={(event) => setSearch(event.target.value)} />
      <div className="admin-screen" /><p className="admin-screen-label">MÀN HÌNH</p>
      <div className="admin-seats" aria-label="Sơ đồ ghế">{rows.map((row) => <div key={row} className="admin-seat-row"><span>{row}</span>
        {seats.filter((seat) => seat.seat_name.startsWith(row) && seat.seat_name.replace(/\d+$/, "") === row).sort((a, b) => Number(a.seat_name.match(/\d+$/)?.[0]) - Number(b.seat_name.match(/\d+$/)?.[0])).map((seat) =>
          <button key={seat.id} className="admin-seat" aria-label={`Sửa ghế ${seat.seat_name}`} title={lookup(data.seat_types, seat.seat_type_id)?.name} onClick={() => setEditor(seat)}>{seat.seat_name}</button>)}</div>)}</div>
      <DataTable columns={[{ key: "seat_name", label: "Vị trí ghế" }, { key: "seat_type_id", label: "Loại ghế", render: (row) => lookup(data?.seat_types, row.seat_type_id)?.name },
        { key: "price", label: "Giá vé", render: (row) => formatCurrency(lookup(data?.seat_types, row.seat_type_id)?.base_price) }]}
        rows={seats} loading={list.loading} error={list.error} reload={list.reload} actions={(row) => <><button onClick={() => setEditor(row)}>Sửa</button><button className="admin-danger" onClick={() => setDeleting(row)}>Xóa</button></>} />
    </section>
    {editor && <Editor title={editor.id ? `Sửa ghế ${editor.seat_name}` : "Thêm ghế"} initial={{ seat_name: editor.seat_name || "", seat_type_id: editor.seat_type_id || "" }} onClose={() => setEditor(null)}
      onSave={async (value) => {
        await api[editor.id ? "put" : "post"](`/admin/rooms/${roomId}/seats${editor.id ? `/${editor.id}` : ""}`, numbers(value, ["seat_type_id"]));
        list.reload(); setNotice("Đã lưu ghế.");
      }}>{(value, set) => <>
        <Field label="Vị trí ghế *" placeholder="Ví dụ: A1" required maxLength={10} pattern="[A-Za-z]+[1-9][0-9]*" value={value.seat_name} onChange={set("seat_name")} />
        <Field label="Loại ghế *" required value={value.seat_type_id} onChange={set("seat_type_id")}><option value="">Chọn loại ghế</option>{options(data.seat_types)}</Field>
      </>}</Editor>}
    {deleting && <ConfirmAction title={`Xóa ghế ${deleting.seat_name}`} description="Ghế đã có đơn vé hoặc đang được giữ sẽ không thể xóa." onClose={() => setDeleting(null)} onConfirm={async () => {
      await api.delete(`/admin/rooms/${roomId}/seats/${deleting.id}`); list.reload(); setNotice("Đã xóa ghế.");
    }} />}
  </>;
}
