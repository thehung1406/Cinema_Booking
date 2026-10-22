import { useCallback, useEffect, useState } from "react";
import api from "../../config/api";

export function errorText(error) {
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => `${item.loc?.at(-1) || "Dữ liệu"}: ${item.msg}`).join("; ");
  return typeof detail === "string" ? detail : "Không thể kết nối máy chủ. Vui lòng thử lại.";
}

export function useAdminData(path, params = {}) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState(null);
  const query = JSON.stringify(params);
  const key = `${path}:${query}:${revision}`;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api.get(path, { params: JSON.parse(query), signal: controller.signal }).then(({ data: result }) => {
      if (!controller.signal.aborted) setResult({ key, data: result, error: "" });
    }).catch((err) => {
      if (!controller.signal.aborted && err.code !== "ERR_CANCELED") setResult({ key, data: null, error: errorText(err) });
    });
    return () => controller.abort();
  }, [path, query, key]);
  const reload = useCallback(() => setRevision((n) => n + 1), []);
  const current = path && result?.key === key ? result : null;
  return { data: current?.data || null, error: current?.error || "", loading: Boolean(path && !current), reload };
}
