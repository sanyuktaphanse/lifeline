// The reminders of GET /reminders/{user_id}, a read that writes nothing (docs/api.md): the due ones first.
export function reminderItems(reply) {
  const due = (reply?.due ?? []).map((item) => ({ ...item, isDue: true }));
  const upcoming = (reply?.upcoming ?? []).map((item) => ({ ...item, isDue: false }));
  return { items: [...due, ...upcoming].map(({ text, due: when, seq, isDue }) => ({ text, due: when ?? null, seq, isDue })), dueCount: due.length };
}
