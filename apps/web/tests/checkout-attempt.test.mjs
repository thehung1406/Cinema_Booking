import test from "node:test";
import assert from "node:assert/strict";
import { attemptScope, readAttempt, saveAttempt } from "../src/services/checkoutAttempt.js";

test("unknown checkout result retries the same body/key after a reload", () => {
  const values = new Map();
  const storage = { getItem: (key) => values.get(key), setItem: (key, value) => values.set(key, value) };
  const scope = attemptScope(7, 11, "reservation-a", [2, 1]);
  const first = saveAttempt(storage, scope, { totalAmount: 150000, foodItems: [] }, "first-key");
  assert.deepEqual(saveAttempt(storage, scope, { totalAmount: 170000, foodItems: [1] }, "new-key"), first);
  assert.deepEqual(readAttempt(storage, scope), first);
  assert.equal(readAttempt(storage, attemptScope(8, 11, "reservation-a", [1, 2])), null);
  assert.equal(readAttempt(storage, attemptScope(7, 11, "reservation-b", [1, 2])), null);
});
