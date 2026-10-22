import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import api from "../../config/api";
import { ConfirmAction, DataTable, Editor, Field, MultiChoice, PageHeading, Pagination } from "./AdminShared";
import { errorText, useAdminData } from "./adminData";

export function EmployeesPage() {
  const session = useOutletContext();
  const canAssign = session.permissions.includes("roles.manage");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [editor, setEditor] = useState(null);
  const [roleEditor, setRoleEditor] = useState(null);
  const [statusEditor, setStatusEditor] = useState(null);
  const [notice, setNotice] = useState("");
  const list = useAdminData("/admin/employees", { q: query, offset, limit: 20 });
  const roles = useAdminData(canAssign ? "/access-control/roles" : null);
  const refresh = (message) => { list.reload(); setNotice(message); };
  return <>
    <PageHeading title="Nhân viên & tài khoản" description="Tạo hồ sơ nhân viên, cập nhật thông tin và quản lý trạng thái truy cập. Có thể tra cứu tài khoản khách hàng để gán vai trò nhân viên."
      createLabel="Thêm nhân viên" onCreate={canAssign ? () => setEditor({}) : undefined} />
    {notice && <p role="status" className="admin-notice">{notice}</p>}
    <section className="admin-panel">
      <div className="admin-toolbar"><Field label="Tra cứu tài khoản" type="search" placeholder="Tên, email hoặc tên đăng nhập" value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0); }} /></div>
      {roles.error && <p className="admin-error" role="alert">{roles.error}</p>}
      <DataTable columns={[
        { key: "full_name", label: "Họ tên", render: (row) => <>{row.full_name || row.username}<small>@{row.username}</small></> },
        { key: "email", label: "Email" }, { key: "phone", label: "Điện thoại" },
        { key: "role", label: "Vai trò", render: (row) => roles.data?.find((role) => role.id === row.role_id)?.name || row.role },
        { key: "is_active", label: "Trạng thái", render: (row) => <span className={`admin-badge ${row.is_active ? "success" : "pending"}`}>{row.is_active ? "Hoạt động" : "Đã khóa"}</span> },
      ]} rows={list.data?.items} loading={list.loading} error={list.error} reload={list.reload}
        actions={(row) => <><button onClick={() => setEditor(row)}>Sửa</button>
          {canAssign && <button disabled={row.id === session.user.id || !roles.data} onClick={() => setRoleEditor(row)}>Vai trò</button>}
          <button className={row.is_active ? "admin-danger" : ""} disabled={row.id === session.user.id} onClick={() => setStatusEditor(row)}>{row.is_active ? "Khóa" : "Mở khóa"}</button></>} />
      <Pagination total={list.data?.total} offset={offset} onChange={setOffset} />
    </section>
    {editor && <Editor title={editor.id ? "Cập nhật tài khoản" : "Thêm nhân viên"}
      initial={{ full_name: editor.full_name || "", email: editor.email || "", phone: editor.phone || "", ...(!editor.id ? { username: "", password: "", role_id: "" } : {}) }}
      onClose={() => setEditor(null)} onSave={async (value) => {
        await api[editor.id ? "put" : "post"](`/admin/employees${editor.id ? `/${editor.id}` : ""}`,
          editor.id ? value : { ...value, role_id: Number(value.role_id) });
        refresh("Đã lưu thông tin tài khoản.");
      }}>{(value, set) => <>
        <Field label="Họ và tên *" required maxLength={100} value={value.full_name} onChange={set("full_name")} />
        <Field label="Email *" required type="email" maxLength={100} value={value.email} onChange={set("email")} />
        <Field label="Điện thoại" type="tel" maxLength={15} value={value.phone} onChange={set("phone")} />
        {!editor.id && <>
          <Field label="Tên đăng nhập *" required minLength={3} maxLength={50} pattern="[a-zA-Z0-9_.-]+" autoComplete="off" value={value.username} onChange={set("username")} />
          <Field label="Mật khẩu ban đầu * (ít nhất 8 ký tự)" required type="password" minLength={8} maxLength={72} autoComplete="new-password" value={value.password} onChange={set("password")} />
          <Field label="Vai trò *" required value={value.role_id} onChange={set("role_id")}><option value="">Chọn vai trò</option>
            {roles.data?.filter((role) => ["ADMIN", "MANAGER", "STAFF"].includes(role.code)).map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</Field>
        </>}
      </>}</Editor>}
    {roleEditor && <Editor title={`Gán vai trò · ${roleEditor.username}`} initial={{ role_id: roleEditor.role_id }} onClose={() => setRoleEditor(null)} onSave={async (value) => {
      await api.put(`/access-control/users/${roleEditor.id}/role`, { role_id: Number(value.role_id) });
      refresh("Đã cập nhật vai trò. Quyền mới có hiệu lực ngay ở máy chủ.");
    }}>{(value, set) => <Field label="Vai trò" required value={value.role_id} onChange={set("role_id")}>{roles.data?.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</Field>}</Editor>}
    {statusEditor && <ConfirmAction title={`${statusEditor.is_active ? "Khóa" : "Mở khóa"} tài khoản ${statusEditor.username}`}
      description={statusEditor.is_active ? "Tài khoản bị khóa sẽ không thể đăng nhập hoặc tiếp tục sử dụng phiên hiện tại." : "Cho phép tài khoản truy cập lại hệ thống."}
      onClose={() => setStatusEditor(null)} onConfirm={async () => {
        await api.put(`/admin/employees/${statusEditor.id}/status`, { is_active: !statusEditor.is_active });
        refresh("Đã cập nhật trạng thái tài khoản.");
      }} />}
  </>;
}

function PermissionEditor({ role, allPermissions, assigned, ownRole, onSaved }) {
  const [chosen, setChosen] = useState(assigned.map((item) => item.id));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <form onSubmit={async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await api.put(`/access-control/roles/${role.id}/permissions`, { permission_ids: chosen });
      onSaved();
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }}>
    {ownRole && <p className="admin-error">Không thể sửa quyền của vai trò mà tài khoản hiện tại đang sử dụng.</p>}
    <fieldset className="admin-form-fields" disabled={busy || ownRole}>
      <MultiChoice label={`Quyền của vai trò ${role.name}`} items={allPermissions.map((permission) => ({ ...permission, name: `${permission.name} (${permission.code})` }))} value={chosen} onChange={setChosen} />
      <div><button className="admin-primary" disabled={busy || ownRole}>{busy ? "Đang lưu…" : "Lưu phân quyền"}</button></div>
    </fieldset>
    {error && <p className="admin-error" role="alert">{error}</p>}
  </form>;
}

export function RolesPage() {
  const session = useOutletContext();
  const [roleId, setRoleId] = useState("");
  const [notice, setNotice] = useState("");
  const roles = useAdminData("/access-control/roles");
  const permissions = useAdminData("/access-control/permissions");
  const selected = roles.data?.find((role) => role.id === Number(roleId)) || roles.data?.[0];
  const assigned = useAdminData(selected ? `/access-control/roles/${selected.id}/permissions` : null);
  return <>
    <PageHeading title="Phân quyền theo vai trò" description="Cấp quyền cụ thể cho từng nhóm nhân viên. Máy chủ kiểm tra quyền ở mỗi thao tác." />
    {notice && <p className="admin-notice" role="status">{notice}</p>}
    <section className="admin-panel">
      <div className="admin-toolbar"><Field label="Vai trò" value={selected?.id || ""} onChange={(event) => { setRoleId(event.target.value); setNotice(""); }}>
        <option value="" disabled>Chọn vai trò</option>
        {roles.data?.map((role) => <option key={role.id} value={role.id}>{role.name} · {role.code}</option>)}</Field></div>
      {(roles.error || permissions.error || assigned.error) && <div><p className="admin-error" role="alert">{roles.error || permissions.error || assigned.error}</p><button onClick={() => { roles.reload(); permissions.reload(); assigned.reload(); }}>Thử lại</button></div>}
      {(roles.loading || permissions.loading || assigned.loading) && <p role="status">Đang tải phân quyền…</p>}
      {selected && permissions.data && assigned.data && !assigned.loading && <PermissionEditor key={`${selected.id}-${assigned.data.map((item) => item.id).join(",")}`}
        role={selected} allPermissions={permissions.data} assigned={assigned.data} ownRole={selected.code === session.user.role}
        onSaved={() => { assigned.reload(); setNotice("Đã lưu phân quyền."); }} />}
    </section>
  </>;
}
