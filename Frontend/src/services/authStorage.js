export const AUTH_SESSION_CHANGED_EVENT = 'loginStatusChanged';
export const USER_INFO_KEY = 'userInfo';
const LEGACY_AUTH_KEYS = ['token', 'isLoggedIn'];

const getBrowserStorage = () => {
  if (typeof window === 'undefined') return null;
  return window.localStorage;
};

const getDispatchEvent = () => {
  if (typeof window === 'undefined') return null;
  return window.dispatchEvent.bind(window);
};

const notifySessionChanged = (dispatchEvent = getDispatchEvent()) => {
  if (!dispatchEvent) return;
  dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
};

const parseUserInfo = (storage) => {
  if (!storage) return null;
  const rawUserInfo = storage.getItem(USER_INFO_KEY);
  if (!rawUserInfo) return null;

  try {
    return JSON.parse(rawUserInfo);
  } catch {
    return null;
  }
};

export const getCurrentUser = ({ storage = getBrowserStorage() } = {}) => {
  return parseUserInfo(storage);
};

export const getAccessToken = ({ storage = getBrowserStorage() } = {}) => {
  const userInfo = parseUserInfo(storage);
  return userInfo?.access_token || null;
};

export const getAuthorizationHeader = (options) => {
  const token = getAccessToken(options);
  return token ? `Bearer ${token}` : null;
};

export const setSession = (
  loginData,
  userData,
  {
    storage = getBrowserStorage(),
    dispatchEvent = getDispatchEvent(),
    notify = true,
  } = {},
) => {
  if (!storage) return null;

  const sessionUser = {
    ...userData,
    access_token: loginData.access_token,
    refresh_token: loginData.refresh_token,
    token_type: loginData.token_type || 'bearer',
  };

  storage.setItem(USER_INFO_KEY, JSON.stringify(sessionUser));
  LEGACY_AUTH_KEYS.forEach((key) => storage.removeItem(key));

  if (notify) notifySessionChanged(dispatchEvent);
  return sessionUser;
};

export const updateCurrentUser = (
  userData,
  {
    storage = getBrowserStorage(),
    dispatchEvent = getDispatchEvent(),
    notify = true,
  } = {},
) => {
  if (!storage) return null;

  const currentUser = parseUserInfo(storage) || {};
  const updatedUser = {
    ...currentUser,
    ...userData,
    access_token: currentUser.access_token,
    refresh_token: currentUser.refresh_token,
    token_type: currentUser.token_type || 'bearer',
  };

  storage.setItem(USER_INFO_KEY, JSON.stringify(updatedUser));

  if (notify) notifySessionChanged(dispatchEvent);
  return updatedUser;
};

export const clearSession = (
  {
    storage = getBrowserStorage(),
    dispatchEvent = getDispatchEvent(),
    notify = true,
  } = {},
) => {
  if (!storage) return;

  storage.removeItem(USER_INFO_KEY);
  LEGACY_AUTH_KEYS.forEach((key) => storage.removeItem(key));

  if (notify) notifySessionChanged(dispatchEvent);
};
