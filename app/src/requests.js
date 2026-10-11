// The bodies the app sends, built in one place so tests can pin them. Nothing here touches the page or the network.

// Typed words and pasted words travel in separate fields and are never joined (docs/api.md, "Pasted text").
// Without typed words there is nothing to send: a paste on its own is never sent.
export function chatBody(userId, typed, pasted, lang) {
  if (typeof typed !== "string" || typed.trim() === "") return null;
  const body = { user_id: userId, text: typed };
  if (typeof pasted === "string" && pasted.trim() !== "") body.pasted_text = pasted;
  body.lang = lang;
  return body;
}

// The token goes back exactly as /chat or /confirm gave it (docs/api.md, "Conventions", point 5).
export function confirmBody(userId, token, lang) {
  return { user_id: userId, confirmation_token: token, lang };
}

// docs/api.md, POST /rescue/start. Only the student's own typed words; the rescue takes no pasted text.
export function rescueStartBody(userId, trigger, typed, lang) {
  if (typeof typed !== "string" || typed.trim() === "") return null;
  return { user_id: userId, trigger, text: typed, lang };
}

// docs/api.md, POST /rescue/step: an answer or a card name in text, or a token to confirm, or neither to continue.
export function rescueStepBody(userId, { text = "", token = null } = {}, lang) {
  const body = { user_id: userId, text };
  if (token !== null) body.confirmation_token = token;
  body.lang = lang;
  return body;
}
