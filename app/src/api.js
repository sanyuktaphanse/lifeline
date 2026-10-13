// Every call to the Lifeline API goes through here. Nothing is cached and nothing is kept in browser storage.

export class ApiError extends Error {
  // status 0 means the server could not be reached at all.
  constructor(status, detail) {
    super(`API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function call(base, method, path, body) {
  let response;
  try {
    response = await fetch(base + path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, null);
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) throw new ApiError(response.status, data && "detail" in data ? data.detail : null);
  return data;
}

export function makeApi(base) {
  const user = (id) => encodeURIComponent(id);
  return {
    health: () => call(base, "GET", "/health"),
    chat: (body) => call(base, "POST", "/chat", body),
    confirm: (body) => call(base, "POST", "/confirm", body),
    rescueStart: (body) => call(base, "POST", "/rescue/start", body),
    rescueStep: (body) => call(base, "POST", "/rescue/step", body),
    ledger: (id) => call(base, "GET", `/ledger/${user(id)}`),
    verify: (id) => call(base, "GET", `/ledger/${user(id)}/verify`),
  };
}
