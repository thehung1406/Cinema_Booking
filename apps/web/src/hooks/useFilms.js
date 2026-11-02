import { useEffect, useState } from "react";
import filmService from "../services/filmService";

export default function useFilms(id) {
  const [data, setData] = useState(id ? null : []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const request = id ? filmService.getFilmDetail(id) : filmService.getFilms();
    request
      .then((value) => {
        if (active) setData(value);
      })
      .catch(() => {
        if (active) setError("Không thể tải thông tin phim. Vui lòng thử lại.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, attempt]);
  return {
    data,
    loading,
    error,
    retry: () => setAttempt((value) => value + 1),
  };
}
