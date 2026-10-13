// Sample data for the hosted preview. Used only when the Lifeline API cannot be reached at all, as on a Netlify link
// where no API runs, so teammates see every screen filled in. Every sample is labelled "Sample" on screen and moves
// nothing. The figures follow the demo fixtures: fixtures/demo_user.yaml and rails/fake_router.py (fees there are
// fixtures too, not published fees). The live demo, with the real API, never uses this file.

const now = Date.now();
const iso = (hoursAgo) => new Date(now - hoursAgo * 3600e3).toISOString();
const ahead = (days) => new Date(now + days * 86400e3).toISOString();

const LEDGER = [
  { seq: 1, ts: iso(70), kind: "receipt", payload: { receipt: { receipt_id: "sim_pix-0001", rail: "sim_pix", amount: "1200", currency: "SGD", status: "completed", simulated: true } } },
  { seq: 2, ts: iso(50), kind: "decision", payload: { decision: { allowed: false, rule_ids: ["R01"] }, action: { type: "transfer" } } },
  { seq: 3, ts: iso(26), kind: "note", payload: { kind: "rescue_started" } },
  { seq: 4, ts: iso(25.9), kind: "execution", payload: { result: { freeze: { status: "done" } } } },
  { seq: 5, ts: iso(25.8), kind: "receipt", payload: { receipt: { receipt_id: "wise-0001", rail: "wise", amount: "300", currency: "SGD", status: "completed", simulated: true } } },
  { seq: 6, ts: iso(25.7), kind: "note", payload: { kind: "family_notice" } },
].map((e) => ({ ...e, actor: "agent", hash: "sample" + String(e.seq).padStart(58, "0"), prev_hash: "" }));

const ROUTES = [
  { rail: "wise", fee: "5.60", currency_from: "SGD", arrival_hours: 24, simulated: false },
  { rail: "sim_pix", fee: "0", currency_from: "SGD", arrival_hours: 0, simulated: true },
  { rail: "bank_wire", fee: "25", currency_from: "SGD", arrival_hours: 72, simulated: false },
];

const done = (text, extra = {}) => ({ text, blocked: [], turn_summary: "This turn: nothing was proposed, changed or sent.", sample: true, ...extra });

function chat(body) {
  const t = (body.text || "").toLowerCase();
  if (body.pasted_text) {
    return done("This looks like a scam: real banks don't ask you to move money to a 'safe account' by message. Don't reply to it, and check in your bank's own app.", {
      blocked: ["Your pasted text asked Lifeline to make a payment. Lifeline did not do that, because only your own words can start an action."],
    });
  }
  if (/rent|landlord/.test(t)) {
    return { text: "Here's your rent payment to check before anything moves.", blocked: [], sample: true,
      turn_summary: "This turn: a transfer of 1200 SGD to landlord_sp: proposed, waiting for your confirmation.",
      confirmation: { confirmation_token: "sample", warning_key: "warn.transfer.irreversible", expires_in_seconds: 300,
        action: { type: "transfer", amount: "1200", currency: "SGD", payee_id: "landlord_sp", purpose: "rent" },
        routes: ROUTES, selected_route: ROUTES[0] } };
  }
  if (/balance/.test(t)) return done("You have 2,300 SGD and 150 BRL.");
  if (/parent|arrived|where/.test(t)) return done("Your parents' transfer from China is with the bank and under review. Banks often check documents at this stage. Nothing for you to do yet; ignore anyone asking you to pay a fee to release it.");
  return done("In the live demo, Lifeline's AI answers here. This preview shows sample replies: try Pay rent, My balance, or attach a message and ask if it's a scam.");
}

let rescueStep = 0;
function rescue(path, body) {
  if (path.endsWith("/start")) { rescueStep = 1; return r("Lifeline started a rescue. First answer the question you set before you left: What are the last four characters of your student pass number?", "S1", "answer_identity_question"); }
  if (rescueStep === 1) { rescueStep = 2; return r("That answer matches your plan. Which card is it?", "S2", "choose_card", { card_names: ["Wise debit card", "Revolut card"] }); }
  if (rescueStep === 2) { rescueStep = 3; return r("Freeze this card now? Payments on it stop until you unfreeze it.", "S2", "confirm_freeze", {}, { confirmation: { confirmation_token: "sample" } }); }
  if (rescueStep === 3) { rescueStep = 4; return r("Your card is frozen. From now on use your backup card, the Revolut card. Do you need emergency money? 300 SGD can go to your own Singapore account.", "S5", "confirm_transfer_or_skip", { live_instrument: "revolut:card_02" }, { confirmation: { confirmation_token: "sample" } }); }
  rescueStep = 0;
  return r("Done. Your Wise card is frozen, payments moved to your Revolut card, and your family has been told.", "done", "done");
}
function r(text, state, doNow, rescueExtra = {}, extra = {}) {
  return { text, blocked: [], sample: true, turn_summary: "This turn: a sample step; nothing was sent.", ...extra,
    rescue: { state_after: state, do_now: doNow, card_names: [], live_instrument: null, issuer_link: null, ...rescueExtra } };
}

export function sample(method, path, body = {}) {
  if (path.startsWith("/reminders/")) return { due: [], upcoming: [{ text: "Rent is due", due: ahead(5) }, { text: "Renew the student pass", due: ahead(20) }] };
  if (path.endsWith("/verify")) return { first_broken_seq: null };
  if (path.startsWith("/ledger/")) return LEDGER;
  if (path === "/chat") return chat(body);
  if (path === "/confirm") return { text: "Done. 1200 SGD was sent over wise. Receipt wise-0002.", blocked: [], sample: true,
    turn_summary: "This turn: a sample confirmation; nothing was sent.",
    receipt: { receipt_id: "wise-0002", rail: "wise", amount: "1200", currency: "SGD", status: "completed", simulated: true } };
  if (path.startsWith("/rescue/")) return rescue(path, body);
  return null;
}
