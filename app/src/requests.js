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
