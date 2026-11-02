import assert from 'node:assert/strict';
import test from 'node:test';
import {
  AUTH_SESSION_CHANGED_EVENT,
  clearSession,
  getAccessToken,
  getCurrentUser,
  setSession,
} from '../src/services/authStorage.js';

const createStorage = () => {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    removeItem: (key) => data.delete(key),
    setItem: (key, value) => data.set(key, String(value)),
  };
};

test('setSession persists userInfo with access token and exposes current user', () => {
  const storage = createStorage();

  setSession(
    {
      access_token: 'access-123',
      refresh_token: 'refresh-123',
      token_type: 'bearer',
    },
    {
      id: 42,
      username: 'alice',
      full_name: 'Alice Tran',
    },
    { storage, notify: false },
  );

  assert.equal(getAccessToken({ storage }), 'access-123');
  assert.deepEqual(getCurrentUser({ storage }), {
    id: 42,
    username: 'alice',
    full_name: 'Alice Tran',
    access_token: 'access-123',
    refresh_token: 'refresh-123',
    token_type: 'bearer',
  });
});

test('clearSession removes every auth key and dispatches the shared event', () => {
  const storage = createStorage();
  const events = [];
  storage.setItem('userInfo', JSON.stringify({ access_token: 'old-token' }));
  storage.setItem('token', 'legacy-token');
  storage.setItem('isLoggedIn', 'true');

  clearSession({
    storage,
    dispatchEvent: (event) => events.push(event.type),
  });

  assert.equal(storage.getItem('userInfo'), null);
  assert.equal(storage.getItem('token'), null);
  assert.equal(storage.getItem('isLoggedIn'), null);
  assert.deepEqual(events, [AUTH_SESSION_CHANGED_EVENT]);
});

test('getAccessToken returns null for missing or malformed userInfo', () => {
  const storage = createStorage();

  assert.equal(getAccessToken({ storage }), null);

  storage.setItem('userInfo', '{bad-json');
  assert.equal(getAccessToken({ storage }), null);
});
