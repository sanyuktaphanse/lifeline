// Whether the confirmation card marks a route Blocked. Only a route the loop would not pay is blocked: one with a
// blocked reason, one over its limit, or one that is down. A degraded route is still offered by the loop, so it is
// not blocked (RouteStatus in contracts/schemas.py: up, degraded, down, simulated).
export function routeBlocked(route) {
  return Boolean(route.blocked_reason) || route.limit_ok === false || route.status === "down";
}
