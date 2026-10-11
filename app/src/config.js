// Where the Lifeline API is. `make dev` serves it on http://127.0.0.1:8000 (docs/api.md, "Running it").
// The address can be changed with ?api= in the page address, but only to another port on this machine,
// because the API itself only accepts calls from localhost (CORS in api/main.py).
const DEFAULT_API = "http://127.0.0.1:8000";
const LOCAL = /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/;

export function apiBase(search) {
  const asked = new URLSearchParams(search).get("api");
  return asked && LOCAL.test(asked) ? asked : DEFAULT_API;
}

// fixture: the demo student of fixtures/demo_user.yaml. There is no sign in yet (docs/api.md, "Security").
export const USER_ID = "student_001";
