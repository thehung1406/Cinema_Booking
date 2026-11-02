/**
 * Dev-only logger utility.
 * Logs are only output when running in development mode (import.meta.env.DEV).
 * In production builds, all log calls are no-ops.
 */
const isDev = typeof import.meta !== 'undefined' && import.meta.env?.DEV;

const logger = {
  debug: (...args) => { if (isDev) console.log('[DEBUG]', ...args); },
  info: (...args) => { if (isDev) console.info('[INFO]', ...args); },
  warn: (...args) => { if (isDev) console.warn('[WARN]', ...args); },
  error: (...args) => { if (isDev) console.error('[ERROR]', ...args); },
};

export default logger;
