// Keep the same body/key when a response is lost, including across page reloads.
export function attemptScope(userId, showtimeId, reservationId, seatIds) {
  return `checkout:${userId}:${showtimeId}:${reservationId || [...seatIds].sort((a, b) => a - b).join(",")}`;
}

export function readAttempt(storage, scope) {
  try {
    const item = JSON.parse(storage.getItem(scope));
    return item?.key && item?.payload ? item : null;
  } catch { return null; }
}

export function saveAttempt(storage, scope, payload, key) {
  const existing = readAttempt(storage, scope);
  if (existing) return existing;
  const item = { key, payload };
  try { storage.setItem(scope, JSON.stringify(item)); } catch { /* Keep this attempt in component state when storage is unavailable. */ }
  return item;
}
