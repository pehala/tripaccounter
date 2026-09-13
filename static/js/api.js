const BASE = '/api/v1';

async function toApiError(res) {
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON (e.g. 500 with an HTML body) */ }
  const error = body && body.error;
  return {
    status: res.status,
    code: error?.code || 'internal_error',
    params: error?.params || {},
    fields: error?.fields || {},
  };
}

async function request(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
  del: (path) => request('DELETE', path),
};
